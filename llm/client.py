import json
import os
import random
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException
from openai import APITimeoutError, APIStatusError, OpenAI

from llm.schema import TriageResponse

load_dotenv()

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "triage1.md"
QUARANTINE_PATH = Path(__file__).parent.parent / "logs" / "quarantine.jsonl"

PROMPT_VERSION = "triage-v1"
MAX_RETRIES = 2
TIMEOUT_SECONDS = 30.0


def load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def save_quarantine(
    text: str,
    error: str,
    input_text: str,
) -> None:
    QUARANTINE_PATH.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "prompt_version": PROMPT_VERSION,
        "input": input_text,
        "raw_output": text,
        "error": error,
    }

    with QUARANTINE_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_call(
    model: str,
    input_tokens: int,
    output_tokens: int,
    duration_ms: int,
    repair_count: int,
) -> None:
    record = {
        "event": "llm_call",
        "prompt_version": PROMPT_VERSION,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "duration_ms": duration_ms,
        "repair_count": repair_count,
    }

    print(json.dumps(record))


def validate_output(text: str) -> TriageResponse:
    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.replace("```json", "", 1)
        cleaned = cleaned.replace("```", "", 1).strip()

    return TriageResponse.model_validate_json(cleaned)


def call_model(
    client: OpenAI,
    messages: list,
) :
    model = os.getenv("LLM_MODEL", "openrouter/free")

    for attempt in range(MAX_RETRIES + 1):
        started = time.perf_counter()

        try:
            response = client.chat.completions.create(
                model=model,
                temperature=0.2,
                messages=messages,
            )

            duration_ms = int(
                (time.perf_counter() - started) * 1000
            )

            usage = response.usage

            input_tokens = usage.prompt_tokens if usage else 0
            output_tokens = usage.completion_tokens if usage else 0

            return response, input_tokens, output_tokens, duration_ms

        except APITimeoutError:
            if attempt >= MAX_RETRIES:
                raise HTTPException(
                    status_code=504,
                    detail="LLM request timed out.",
                )

            delay = (2 ** attempt) + random.uniform(0, 0.5)
            time.sleep(delay)

        except APIStatusError as error:
            status = error.status_code

            if status == 429 or status >= 500:
                if attempt >= MAX_RETRIES:
                    raise HTTPException(
                        status_code=502,
                        detail="LLM provider unavailable after retries.",
                    )

                delay = (2 ** attempt) + random.uniform(0, 0.5)
                time.sleep(delay)
                continue

            if status in (400, 401, 403):
                raise HTTPException(
                    status_code=502,
                    detail=f"LLM provider rejected the request: HTTP {status}.",
                )

            raise HTTPException(
                status_code=502,
                detail="LLM provider returned an unexpected error.",
            )

    raise HTTPException(
        status_code=502,
        detail="LLM request failed.",
    )


def triage_with_llm(text: str) -> TriageResponse:

    if os.getenv("LLM_ENABLED", "true").lower() == "false":
        return TriageResponse(
            category="other",
            urgency="normal",
            confidence=0.0,
            reason="LLM disabled by configuration.",
        )

    client = OpenAI(
        base_url=os.getenv("LLM_BASE_URL"),
        api_key=os.getenv("LLM_API_KEY"),
        timeout=TIMEOUT_SECONDS,
        max_retries=0,
    )

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

    response, input_tokens, output_tokens, duration_ms = call_model(
        client,
        messages,
    )

    content = response.choices[0].message.content or ""

    try:
        result = validate_output(content)

        log_call(
            os.getenv("LLM_MODEL", "openrouter/free"),
            input_tokens,
            output_tokens,
            duration_ms,
            0,
        )

        return result

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
                    "Your previous answer was rejected.\n"
                    f"Validation error: {first_error}\n\n"
                    "Return only corrected JSON matching the required schema."
                ),
            },
        ]

        (
            repair_response,
            repair_input_tokens,
            repair_output_tokens,
            repair_duration_ms,
        ) = call_model(
            client,
            repair_messages,
        )

        repaired_content = (
            repair_response.choices[0].message.content or ""
        )

        try:
            result = validate_output(repaired_content)

            log_call(
                os.getenv("LLM_MODEL", "openrouter/free"),
                input_tokens + repair_input_tokens,
                output_tokens + repair_output_tokens,
                duration_ms + repair_duration_ms,
                1,
            )

            return result

        except Exception as second_error:

            save_quarantine(
                repaired_content,
                str(second_error),
                text,
            )

            log_call(
                os.getenv("LLM_MODEL", "openrouter/free"),
                input_tokens + repair_input_tokens,
                output_tokens + repair_output_tokens,
                duration_ms + repair_duration_ms,
                1,
            )

            raise HTTPException(
                status_code=422,
                detail="LLM output failed validation after one repair attempt.",
            )