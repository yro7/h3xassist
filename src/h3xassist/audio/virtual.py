import asyncio
import json
import logging
import re
import shutil
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_SINK_LINE_RX = re.compile(r"^\s*(\d+)\.\s+(.*?)\s+\[vol: ")


class PactlNotFoundError(RuntimeError):
    """Raised when pactl is not available."""


def _require_pactl() -> None:
    if shutil.which("pactl") is None:
        msg = "pactl not found. Install pulseaudio-utils (pipewire-pulse client)."
        raise PactlNotFoundError(msg)


async def _run(*cmd: str) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out_b, err_b = await proc.communicate()
    return proc.returncode or 0, out_b.decode(), err_b.decode()


async def _pw_dump() -> list[dict[str, Any]]:
    code, out, err = await _run("pw-dump")
    if code != 0:
        raise RuntimeError(f"pw-dump failed: {err.strip()}")
    return cast("list[dict[str, Any]]", json.loads(out))


def _extract_props(obj: dict[str, Any]) -> dict[str, Any]:
    """Extract PipeWire object properties from nested structure."""
    return (
        cast("dict[str, Any]", (obj.get("info", {}).get("props", {})))
        if isinstance(obj, dict)
        else {}
    )


async def _find_sink_node(desc: str, name: str) -> tuple[int, str] | None:
    """Find created sink node by description/nick or pulse name.

    Returns (node_id, object_serial) if found.
    """
    data = await _pw_dump()
    for obj in data:
        if obj.get("type") != "PipeWire:Interface:Node":
            continue
        props = _extract_props(obj)
        if props.get("media.class") != "Audio/Sink":
            continue
        node_id = obj.get("id")
        serial = props.get("object.serial")
        node_desc = props.get("node.description") or ""
        node_nick = props.get("node.nick") or ""
        node_name = props.get("node.name") or ""
        pulse_name = props.get("pulse.name") or ""
        if (
            (node_desc == desc or node_nick == desc or pulse_name == name or name in node_name)
            and node_id is not None
            and serial
        ):
            return int(node_id), str(serial)
    return None


@dataclass
class CreatedSink:
    pactl_module_id: int
    sink_name: str
    node_id: int
    object_serial: str


async def cleanup_orphaned_sinks(name_prefix: str = "h3xassist") -> int:
    """Remove orphaned h3xassist audio sinks from previous sessions.

    Args:
        name_prefix: Prefix to identify sinks to cleanup

    Returns:
        Number of orphaned sinks removed
    """
    _require_pactl()
    logger = logging.getLogger(__name__)

    # Get list of loaded modules
    code, out, err = await _run("pactl", "list", "modules", "short")
    if code != 0:
        logger.warning("Failed to list pactl modules: %s", err.strip())
        return 0

    removed_count = 0
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3:
            module_id = parts[0]
            module_name = parts[1]

            # Check if this is a null-sink module
            if module_name == "module-null-sink":
                # Get module info to check sink name
                code, info_out, _ = await _run("pactl", "list", "modules")
                if (
                    code == 0
                    and f"Module #{module_id}" in info_out
                    and f"sink_name={name_prefix}." in info_out
                ):
                    # Find the section for this module
                    module_section = info_out.split(f"Module #{module_id}")[1].split("Module #")[0]
                    if f"sink_name={name_prefix}." in module_section:
                        logger.info("Removing orphaned sink module: %s", module_id)
                        await _run("pactl", "unload-module", module_id)
                        removed_count += 1

    if removed_count > 0:
        logger.info("Cleaned up %d orphaned audio sinks", removed_count)

    return removed_count


@asynccontextmanager
async def virtual_sink(
    *, name_prefix: str = "h3xassist", description: str | None = None
) -> "AsyncIterator[CreatedSink]":
    """Create a temporary null sink via pactl (pipewire-pulse).

    Resolves the created sink to a PipeWire node id and object.serial
    for use with pw-record / pw-play.

    Args:
        name_prefix: Prefix for unique sink name generation
        description: Human-readable description (defaults to generated name)

    Yields:
        CreatedSink with pactl module info and PipeWire node details
    """
    _require_pactl()

    sink_name = f"{name_prefix}.{uuid.uuid4().hex[:8]}"
    sink_desc = description or sink_name
    logger = logging.getLogger(__name__)

    # Create the sink
    code, out, err = await _run(
        "pactl",
        "load-module",
        "module-null-sink",
        f"sink_name={sink_name}",
        f'sink_properties=node.description="{sink_desc}",node.nick="{sink_desc}"',
    )
    if code != 0:
        raise RuntimeError(f"Failed to load module-null-sink: {err.strip()}")
    module_id = int(out.strip())

    try:
        # Wait for sink to appear in PipeWire
        start = time.monotonic()
        found: tuple[int, str] | None = None
        while time.monotonic() - start < 5.0:
            found = await _find_sink_node(sink_desc, sink_name)
            if found:
                break
            await asyncio.sleep(0.05)

        if not found:
            raise RuntimeError("Failed to resolve created null sink")

        node_id, serial = found
        created = CreatedSink(
            pactl_module_id=module_id,
            sink_name=sink_name,
            node_id=node_id,
            object_serial=serial,
        )

        logger.info(
            "created null sink: name=%s node_id=%s serial=%s",
            created.sink_name,
            created.node_id,
            created.object_serial,
        )

        yield created

    finally:
        # Cleanup sink
        await _run("pactl", "unload-module", str(module_id))
        logger.debug(
            "unloaded null sink: name=%s module_id=%s",
            sink_name,
            module_id,
        )
