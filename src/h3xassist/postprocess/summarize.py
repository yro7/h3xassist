import asyncio
import logging
import random
from typing import cast

from google import genai
from google.genai import types
from google.genai.errors import ClientError, ServerError

from h3xassist.models.summary import MeetingSummary
from h3xassist.settings import settings

logger = logging.getLogger(__name__)


class SummarizationService:
    """LLM-backed summarization over full transcript text using google-genai.

    Requires a valid Google API key provided via settings or environment.
    """

    def __init__(
        self,
        *,
        model_name: str,
        summary_language: str | None,
        temperature: float,
        provider_token: str,
    ) -> None:
        self.model_name = model_name
        self.summary_language = summary_language
        self.temperature = temperature
        self._client = genai.Client(api_key=(provider_token))

    async def summarize(self, *, transcript_text: str) -> MeetingSummary:
        max_chars = int(settings.summarization.max_chars)
        text = transcript_text[:max_chars]

        prompt = self._build_prompt(text, self.summary_language)

        # Prepare generation config for JSON-typed response
        generation_config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=MeetingSummary,
        )

        logger.info("Summarizing meeting with model %s", self.model_name)

        max_attempts = settings.summarization.retry_max_attempts
        delay = settings.summarization.retry_initial_delay_sec
        backoff = settings.summarization.retry_backoff_multiplier
        max_delay = settings.summarization.retry_max_delay_sec
        jitter = settings.summarization.retry_jitter_sec
        retryable_codes = set(settings.summarization.retry_status_codes)

        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                response = await self._client.aio.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=generation_config,
                )
                return cast("MeetingSummary", response.parsed)
            except (ServerError, ClientError) as e:
                last_error = e
                status = getattr(e, "status_code", None) or getattr(e, "code", None)
                if status in retryable_codes and attempt < max_attempts:
                    sleep_sec = min(max_delay, delay) + random.uniform(0.0, max(0.0, jitter))
                    logger.warning(
                        "Summarization attempt %s/%s failed with status %s. Retrying in %.2fs...",
                        attempt,
                        max_attempts,
                        status,
                        sleep_sec,
                    )
                    await asyncio.sleep(sleep_sec)
                    delay = min(max_delay, delay * backoff)
                    continue
                else:
                    logger.exception(
                        "google-genai generate failed (non-retryable or exhausted): %s", e
                    )
                    break
            except Exception as e:  # network/unknown
                last_error = e
                if attempt < max_attempts:
                    sleep_sec = min(max_delay, delay) + random.uniform(0.0, max(0.0, jitter))
                    logger.warning(
                        "Summarization attempt %s/%s raised %s. Retrying in %.2fs...",
                        attempt,
                        max_attempts,
                        e.__class__.__name__,
                        sleep_sec,
                    )
                    await asyncio.sleep(sleep_sec)
                    delay = min(max_delay, delay * backoff)
                    continue
                logger.exception("google-genai generate failed after retries")
                break

        if last_error:
            raise last_error

        # unreachable code, but required for type checking
        raise RuntimeError("Summarization failed")

    def _build_prompt(self, text: str, summary_language: str | None) -> str:
        lang_clause = (
            f"Write the summary in {summary_language}."
            if summary_language
            else "Write the summary in the same language as the transcript."
        )
        return (
            "You are an expert meeting assistant working with ASR transcripts.\n"
            "The transcript may contain recognition errors (e.g., 'SAAR' instead of 'SOAR'), hallucinated phrases, or stray noise like 'Thanks for watching!'.\n"
            "Your tasks:\n"
            "- Correct terminology, names, acronyms and noisy phrases using context.\n"
            "- Remove unrelated filler/noise and consolidate duplicated statements.\n"
            "- Produce a structured JSON object that strictly matches the provided response schema.\n"
            "- Owners fields are arrays of plain human names (no emails or usernames).\n"
            f"- Prioritize labeling action items owned by '{settings.general.notes_owner_handle or ''}' under a separate 'my_actions' list. If unknown or not present, leave 'my_actions' empty.\n"
            f"- {lang_clause}\n"
            "- Do NOT output Markdown; produce only structured fields.\n\n"
            "Focus on accuracy, clarity, and actionability.\n\n"
            "Transcript begins below:\n\n"
            f"{text}"
        )
