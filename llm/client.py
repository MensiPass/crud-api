import json
from pathlib import Path

import os
from dotenv import load_dotenv
from openai import OpenAI

from llm.schema import TriageResponse

load_dotenv()

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "triage1.md"
QUARANTINE_PATH = Path(__file__).parent.parent / "logs" / "quarantine.jsonl"


def load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def save_quarantine(text: str, error: str, input_text: str) -> None:
    QUARANTINE_PATH.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "input": input_text,
        "raw_output": text,
        "error": error,
    }

    with QUARANTINE_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def validate_output(text: str) -> TriageResponse:
    cleaned = text.strip()

    # Handle accidental Markdown code fences.
    if cleaned.startswith("```"):
        cleaned = cleaned.replace("```json", "", 1)
        cleaned = cleaned.replace("```", "", 1).strip()

    return TriageResponse.model_validate_json(cleaned)


def triage_with_llm(text: str) -> TriageResponse:
    client = OpenAI(
        base_url=os.getenv("LLM_BASE_URL"),
        api_key=os.getenv("LLM_API_KEY"),
    )

    prompt = load_prompt()

    response = client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "openrouter/free"),
        messages=[
            {
                "role": "system",
                "content": prompt,
            },
            {
                "role": "user",
                "content": text,
            },
        ],
    )

    content = response.choices[0].message.content or ""

    # First validation attempt.
    try:
        return validate_output(content)

    except Exception as first_error:

        # Exactly ONE repair attempt.
        repair_response = client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "openrouter/free"),
            messages=[
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
            ],
        )

        repaired_content = (
            repair_response.choices[0].message.content or ""
        )

        # Second validation attempt.
        try:
            return validate_output(repaired_content)

        except Exception as second_error:

            # Both attempts failed.
            save_quarantine(
                repaired_content,
                str(second_error),
                text,
            )

            raise ValueError(
                "LLM output failed validation after one repair attempt."
            ) from second_error