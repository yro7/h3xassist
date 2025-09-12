import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from O365 import Account
from O365.utils.token import FileSystemTokenBackend

from h3xassist.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class CalendarEvent:
    """Calendar event from Outlook integration."""

    event_id: str
    subject: str
    start: str | None
    end: str | None
    online_meeting_url: str | None = None


class OutlookClient:
    def __init__(self) -> None:
        if settings.integrations.outlook is None:
            raise RuntimeError("Outlook settings are not configured; run 'h3xassist configure'")
        self.tenant_id = settings.integrations.outlook.tenant_id
        self.client_id = settings.integrations.outlook.client_id
        self.user_email = settings.integrations.outlook.user_email
        # O365 token backend (file on disk)
        token_file_path = Path(settings.integrations.outlook.token_cache_path).expanduser()
        token_path = str(token_file_path.parent)
        token_name = token_file_path.name
        self._token_backend = FileSystemTokenBackend(
            token_path=token_path, token_filename=token_name
        )
        self._account = Account(
            credentials=self.client_id,
            tenant_id=self.tenant_id,
            token_backend=self._token_backend,
            auth_flow_type="public",
        )

    # login flow is handled by CLI (ms-login); client only uses cached tokens

    async def list_upcoming(self) -> list[CalendarEvent]:
        def _list() -> list[CalendarEvent]:
            if not self._account.is_authenticated:
                raise RuntimeError("Outlook not authorized; run 'h3xassist ms-login' first")
            schedule = self._account.schedule(resource=self.user_email)
            calendar = schedule.get_default_calendar()
            now = datetime.now(UTC)
            end = now + timedelta(hours=24)

            def _fmt(dt: datetime) -> str:
                return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

            events_iter = calendar.get_events(
                include_recurring=True,
                start_recurring=_fmt(now),
                end_recurring=_fmt(end),
                limit=20,
            )
            out: list[CalendarEvent] = []
            for ev in events_iter:
                try:
                    join_url = None
                    try:
                        online = getattr(ev, "online_meeting", None)
                        if isinstance(online, dict):
                            join_url = online.get("joinUrl")
                    except Exception:
                        pass

                    event = CalendarEvent(
                        event_id=ev.object_id,
                        subject=ev.subject,
                        start=ev.start.isoformat() if ev.start else None,
                        end=ev.end.isoformat() if ev.end else None,
                        online_meeting_url=join_url,
                    )
                    out.append(event)
                except Exception:
                    continue
            return out

        return await asyncio.to_thread(_list)
