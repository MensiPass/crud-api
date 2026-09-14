import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from llm.schema import TriageResponse

load_dotenv()

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "triage1.md"


def load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def triage_with_llm(text: str) -> TriageResponse:
    client = OpenAI(
        base_url=os.getenv("LLM_BASE_URL"),
        api_key=os.getenv("LLM_API_KEY"),
    )

    response = client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "openrouter/free"),
        messages=[
            {
                "role": "system",
                "content": load_prompt(),
            },
            {
                "role": "user",
                "content": text,
            },
        ],
    )

    content = response.choices[0].message.content

    return TriageResponse.model_validate_json(content)