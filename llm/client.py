import json
import os
import random
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import (
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
)

from llm.schema import TriageResponse

load_dotenv()

BASE_DIR = Path(__file__).parent.parent

PROMPT_PATH = BASE_DIR / "prompts" / "triage1.md"
QUARANTINE_PATH = BASE_DIR / "logs" / "quarantine.jsonl"
CALL_LOG_PATH = BASE_DIR / "logs" / "llm_calls.jsonl"

PROMPT_VERSION = "triage-v1"

MAX_ATTEMPTS = 3
TIMEOUT_SECONDS = 30.0


class LLMTimeoutError(Exception):
    pass


class LLMAuthenticationError(Exception):
    pass


class LLMUnavailableError(Exception):
    pass


def load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def log_call(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    duration_ms: float,
    repair_count: int,
    attempt: int,
    success: bool,
    error: str | None = None,
) -> None:
    CALL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "prompt_version": PROMPT_VERSION,
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "duration_ms": round(duration_ms, 2),
        "repair_count": repair_count,
        "attempt": attempt,
        "success": success,
    }

    if error:
        record["error"] = error

    with CALL_LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def save_quarantine(
    text: str,
    error: str,
    input_text: str,
) -> None:
    QUARANTINE_PATH.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "input": input_text,
        "raw_output": text,
        "error": error,
        "prompt_version": PROMPT_VERSION,
    }

    with QUARANTINE_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def extract_json_object(text: str) -> str:
    cleaned = text.strip()

    if cleaned.startswith("```"):
        lines = cleaned.splitlines()

        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        cleaned = "\n".join(lines).strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start != -1 and end != -1 and end > start:
        return cleaned[start:end + 1]

    return cleaned


def validate_output(text: str) -> TriageResponse:
    cleaned = extract_json_object(text)
    return TriageResponse.model_validate_json(cleaned)


def create_client() -> OpenAI:
    return OpenAI(
        base_url=os.getenv("LLM_BASE_URL"),
        api_key=os.getenv("LLM_API_KEY"),
        timeout=TIMEOUT_SECONDS,
        max_retries=0,
    )


def should_retry(error: Exception) -> bool:
    if isinstance(error, APITimeoutError):
        return True

    if isinstance(error, APIStatusError):
        status = error.status_code
        return status == 429 or 500 <= status <= 599

    return False


def call_model(
    client: OpenAI,
    messages: list[dict],
    repair_count: int,
) -> str:
    model = os.getenv("LLM_MODEL", "openrouter/free")

    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        start = time.perf_counter()

        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.1,
            )

            duration_ms = (time.perf_counter() - start) * 1000

            usage = response.usage

            prompt_tokens = (
                usage.prompt_tokens
                if usage and usage.prompt_tokens is not None
                else 0
            )

            completion_tokens = (
                usage.completion_tokens
                if usage and usage.completion_tokens is not None
                else 0
            )

            content = response.choices[0].message.content or ""

            log_call(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                duration_ms=duration_ms,
                repair_count=repair_count,
                attempt=attempt,
                success=True,
            )

            return content

        except AuthenticationError as error:
            duration_ms = (time.perf_counter() - start) * 1000

            log_call(
                model=model,
                prompt_tokens=0,
                completion_tokens=0,
                duration_ms=duration_ms,
                repair_count=repair_count,
                attempt=attempt,
                success=False,
                error="authentication_error",
            )

            raise LLMAuthenticationError(
                "LLM authentication failed."
            ) from error

        except APITimeoutError as error:
            duration_ms = (time.perf_counter() - start) * 1000

            log_call(
                model=model,
                prompt_tokens=0,
                completion_tokens=0,
                duration_ms=duration_ms,
                repair_count=repair_count,
                attempt=attempt,
                success=False,
                error="timeout",
            )

            last_error = error

        except APIStatusError as error:
            duration_ms = (time.perf_counter() - start) * 1000
            status = error.status_code

            log_call(
                model=model,
                prompt_tokens=0,
                completion_tokens=0,
                duration_ms=duration_ms,
                repair_count=repair_count,
                attempt=attempt,
                success=False,
                error=f"http_{status}",
            )

            if status in (400, 401, 403):
                if status == 401:
                    raise LLMAuthenticationError(
                        "LLM authentication failed."
                    ) from error

                raise LLMUnavailableError(
                    f"LLM request failed with HTTP {status}."
                ) from error

            if not should_retry(error):
                raise LLMUnavailableError(
                    f"LLM request failed with HTTP {status}."
                ) from error

            last_error = error

        if attempt < MAX_ATTEMPTS:
            delay = min(
                2 ** (attempt - 1) + random.uniform(0, 0.5),
                8,
            )
            time.sleep(delay)

    if isinstance(last_error, APITimeoutError):
        raise LLMTimeoutError(
            "LLM request timed out after retries."
        ) from last_error

    raise LLMUnavailableError(
        "LLM provider unavailable after retries."
    ) from last_error


def deterministic_fallback() -> TriageResponse:
    return TriageResponse(
        category="other",
        urgency="normal",
        confidence=0.0,
        reason="LLM disabled; deterministic fallback used.",
    )


def stub_response() -> TriageResponse:
    return TriageResponse(
        category="feature",
        urgency="low",
        confidence=1.0,
        reason="Stub response for local testing.",
    )


def triage_with_llm(text: str) -> TriageResponse:
    if os.getenv("LLM_ENABLED", "true").lower() == "false":
        return deterministic_fallback()

    if os.getenv("LLM_STUB", "0") == "1":
        return stub_response()

    client = create_client()
    prompt = load_prompt()

    messages = [
        {
            "role": "system",
            "content": prompt,
        },
        {
            "role": "user",
            "content": text,
        },
    ]

    content = call_model(
        client=client,
        messages=messages,
        repair_count=0,
    )

    try:
        return validate_output(content)

    except Exception as first_error:
        repair_messages = [
            {
                "role": "system",
                "content": prompt,
            },
            {
                "role": "user",
                "content": text,
            },
            {
                "role": "assistant",
                "content": content,
            },
            {
                "role": "user",
                "content": (
                    "Your previous response was invalid.\n"
                    f"Validation error: {first_error}\n\n"
                    "Return only corrected JSON that matches "
                    "the required schema."
                ),
            },
        ]

        repaired_content = call_model(
            client=client,
            messages=repair_messages,
            repair_count=1,
        )

        try:
            return validate_output(repaired_content)

        except Exception as second_error:
            save_quarantine(
                repaired_content,
                str(second_error),
                text,
            )

            raise ValueError(
                "LLM output failed validation after one repair attempt."
            ) from second_error