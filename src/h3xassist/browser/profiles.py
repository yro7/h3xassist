import asyncio
import contextlib
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


_EXCLUDE_PATTERNS = (
    "Singleton*",
    "*.lock",
    "LOCK",
    "Crashpad",
    "GPUCache",
    "Code Cache",
    "ShaderCache",
    "DawnCache",
    os.path.join("Service Worker", "CacheStorage"),
)


@contextlib.asynccontextmanager
async def temp_profile_from_base(*, profile_name: str, profiles_dir: Path) -> "AsyncIterator[str]":
    """Yield path to a temporary profile created via reflink from a base profile.

    Ensures cleanup on exit.
    """
    from h3xassist.errors import ProfileNotFoundError

    base_dir = profiles_dir / profile_name

    # Check that base profile exists BEFORE creating temp directory
    if not base_dir.exists():
        raise ProfileNotFoundError(profile_name)

    tmp_dir = Path(tempfile.mkdtemp(prefix="h3xassist_prof_"))
    logger.info("Creating temp profile via reflink: src=%s dst=%s", base_dir, tmp_dir)

    try:
        proc = await asyncio.create_subprocess_exec(
            "cp",
            "-a",
            "--reflink=auto",
            str(base_dir / "."),
            str(tmp_dir),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"cp reflink failed: {stderr.decode(errors='ignore').strip()}")

        for pattern in _EXCLUDE_PATTERNS:
            for p in tmp_dir.glob(pattern):
                with contextlib.suppress(Exception):
                    if p.is_dir():
                        shutil.rmtree(p)
                    else:
                        p.unlink()
        yield str(tmp_dir)
    finally:
        with contextlib.suppress(Exception):
            shutil.rmtree(tmp_dir, ignore_errors=True)
