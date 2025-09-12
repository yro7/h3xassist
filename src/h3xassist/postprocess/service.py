import asyncio
import contextlib
import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from h3xassist.models.recording import RecordingStatus
from h3xassist.storage.recording_store import RecordingStore

if TYPE_CHECKING:
    from uuid import UUID

    from h3xassist.postprocess.pipeline import Pipeline
    from h3xassist.storage.recording_store import RecordingStore

logger = logging.getLogger(__name__)


class ProcessingResult(Enum):
    """Result of processing a recording."""

    SUCCESS = "success"
    ERROR = "error"


@dataclass
class ProcessingComplete:
    """Notification when processing is complete."""

    recording_id: "UUID"
    result: ProcessingResult
    error: Exception | None = None


class PostprocessService:
    """Async background service that processes recordings with limited concurrency."""

    def __init__(
        self, pipeline: "Pipeline", store: "RecordingStore", *, max_concurrency: int
    ) -> None:
        self._pipeline = pipeline
        self._queue: asyncio.Queue[UUID] = asyncio.Queue()
        self._results_queue: asyncio.Queue[ProcessingComplete] = asyncio.Queue()
        self._stop = asyncio.Event()
        self._sema = asyncio.Semaphore(max_concurrency)
        self._task: asyncio.Task[None] | None = None
        self._processing_tasks: set[asyncio.Task[None]] = set()
        self._store = store

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Stop the postprocess service."""
        self._stop.set()
        if self._task:
            with contextlib.suppress(Exception):
                await self._task

        logger.info("Waiting for %d processing tasks to complete", len(self._processing_tasks))
        await asyncio.gather(*self._processing_tasks)

    def enqueue(self, recording_id: "UUID") -> None:
        self._queue.put_nowait(recording_id)

    async def get_next_result(self) -> ProcessingComplete:
        """Get next processing result (blocks until available)."""
        return await self._results_queue.get()

    async def _run(self) -> None:
        logger.info("Starting postprocess service (concurrency=%s)", self._sema._value)
        try:
            while not self._stop.is_set():
                try:
                    recording_id = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                except TimeoutError:
                    continue
                task = asyncio.create_task(self._process_recording(recording_id))
                self._processing_tasks.add(task)
                task.add_done_callback(self._processing_tasks.discard)
        finally:
            logger.info(
                "Postprocess service stopped (processing tasks=%d)", len(self._processing_tasks)
            )

    async def _process_recording(self, recording_id: "UUID") -> None:
        async with self._sema:
            try:
                handle = self._store.get(recording_id)
                # Skip if already postprocessed
                st = handle.read_meta()
                if st is not None and st.status != RecordingStatus.READY:
                    logger.info("Skipping not ready recording: %s", recording_id)
                    return
                st.status = RecordingStatus.PROCESSING
                handle.write_meta(st)
                await self._pipeline.process(handle)
                logger.info("Successfully processed recording: %s", recording_id)

                st = handle.read_meta()
                assert st is not None

                st.status = RecordingStatus.COMPLETED
                handle.write_meta(st)

                # Notify completion via results queue
                await self._results_queue.put(
                    ProcessingComplete(recording_id=recording_id, result=ProcessingResult.SUCCESS)
                )
            except Exception as e:
                logger.exception("Postprocessing failed for %s", recording_id)

                # Notify error via results queue
                await self._results_queue.put(
                    ProcessingComplete(
                        recording_id=recording_id, result=ProcessingResult.ERROR, error=e
                    )
                )
