import importlib.resources as pkg_resources
import logging
from typing import TYPE_CHECKING, Any

from jinja2 import Environment

from h3xassist.models.recording import Transcript
from h3xassist.postprocess.pipeline import ProcessingStage

if TYPE_CHECKING:
    from pathlib import Path

    from h3xassist.models.summary import MeetingSummary
    from h3xassist.postprocess.pipeline import ProcessingContext

logger = logging.getLogger(__name__)


class ExportStage(ProcessingStage):
    """Consolidated stage for all file exports and persistence."""

    def __init__(
        self,
        *,
        export_obsidian: bool,
        obsidian_base_dir: "Path | None",
    ) -> None:
        self._export_obsidian = export_obsidian
        self._obsidian_base_dir = obsidian_base_dir

    @property
    def name(self) -> str:
        return "export"

    async def process(self, context: "ProcessingContext") -> "ProcessingContext":
        """Export all configured outputs."""

        await self._export_transcript_json(context)
        await self._export_summary_json(context)

        if self._export_obsidian:
            await self._export_obsidian_markdown(context)

        meta = context.handle.read_meta()
        assert meta is not None

        logger.info("Exported recording %s", meta.id)
        return context

    async def _export_transcript_json(self, context: "ProcessingContext") -> None:
        """Export transcript segments to RecordingStore (transcript.json)."""
        if not context.segments:
            logger.warning("No segments to export")
            return

        context.handle.write_transcript(Transcript(segments=context.segments))
        logger.debug("Persisted %d segments to transcript.json", len(context.segments))

    async def _export_summary_json(self, context: "ProcessingContext") -> None:
        """Export summary as JSON file in recording directory."""
        if not context.summary:
            logger.warning("No summary to export")
            return

        context.handle.write_summary(context.summary)
        logger.debug("Saved summary.json")

    async def _export_obsidian_markdown(self, context: "ProcessingContext") -> None:
        """Export summary as markdown file to Obsidian directory."""
        if not context.summary:
            logger.warning("No summary to export to Obsidian")
            return

        if not self._obsidian_base_dir:
            logger.warning("No Obsidian base directory to export to")
            return

        meta = context.handle.read_meta()
        if meta is None:
            logger.warning("No metadata to export to Obsidian")  # type: ignore[unreachable]
            return

        date_str = meta.scheduled_start.strftime("%Y.%m.%d %H.%M")
        duration_hms = None
        attendees_list: list[str] = []

        if meta.duration_sec is not None:
            total = max(0, int(meta.duration_sec))
            h = total // 3600
            m = (total % 3600) // 60
            s = total % 60
            duration_hms = f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

        captions_intervals = context.handle.read_caption_intervals()

        if captions_intervals is not None:
            names = {ci.speaker.strip() for ci in captions_intervals.intervals}
            attendees_list = sorted(n for n in names if n)

        # Generate markdown
        md = self._build_markdown(
            context.summary,
            date=date_str,
            subject=meta.subject,
            source=meta.url,
            attendees=attendees_list,
            duration_hms=duration_hms or "",
        )

        # Save to Obsidian directory
        try:
            out_dir = self._obsidian_base_dir
            out_dir.mkdir(parents=True, exist_ok=True)

            date_human = meta.scheduled_start.astimezone().strftime("%Y.%m.%d %H.%M")
            title_token = meta.subject.strip()
            title_token = title_token.replace("/", "-").replace("\\", "-")
            title_token = " ".join(title_token.split())[:120]
            base_name = f"{date_human} - {title_token}".strip()
            md_dst = out_dir / f"{base_name}.md"

            with open(md_dst, "w", encoding="utf-8") as fh:
                fh.write(md)

            logger.debug("Exported summary to Obsidian: %s", md_dst)

        except Exception:
            logger.exception("Failed to export summary to Obsidian")

    def _build_markdown(
        self,
        summary: "MeetingSummary",
        *,
        date: str,
        subject: str,
        source: str,
        attendees: list[str],
        duration_hms: str,
    ) -> str:
        """Render Markdown using external Jinja2 template."""
        context: dict[str, Any] = {
            "tags": ["meeting", "summary"],
            "date": date,
            "subject": subject,
            "source": source,
            "attendees": attendees,
            "duration": duration_hms,
            "summary": summary,
        }
        template_path = pkg_resources.files("h3xassist.postprocess").joinpath("summary.md.j2")
        template_text = template_path.read_text(encoding="utf-8")
        env = Environment(autoescape=False, trim_blocks=True, lstrip_blocks=True)
        template = env.from_string(template_text)
        return template.render(**context)
