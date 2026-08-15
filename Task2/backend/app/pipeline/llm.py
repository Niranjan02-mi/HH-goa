"""
General LLM abstraction for handling GENERAL_LLM route without claiming web knowledge.
"""
from groq import AsyncGroq
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings
from app.utils.latency import timed_ms
from app.pipeline.prompts import GENERAL_PROMPT

_client: AsyncGroq | None = None

def get_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=settings.groq_api_key)
    return _client

@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=0.3, min=0.3, max=1.0),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def generate_general_answer(query: str, language_name: str) -> tuple[str, float]:
    """Generate a general answer using the LLM without external evidence."""
    client = get_client()
    
    # We explicitly tell it the language to answer in
    lang_instruction = f"Answer in {language_name}."

    with timed_ms() as timing:
        response = await client.chat.completions.create(
            model=settings.generation_model,
            messages=[
                {"role": "system", "content": GENERAL_PROMPT + "\n" + lang_instruction},
                {"role": "user", "content": query},
            ],
            max_tokens=settings.max_gen_tokens,
            temperature=0.7,  # Higher temperature for general generation
        )

    answer = response.choices[0].message.content or ""
    return answer, timing["ms"]

async def generate_general_answer_stream(query: str, language_name: str):
    """Yield chunks of a general answer using the LLM without external evidence."""
    client = get_client()
    
    lang_instruction = f"Answer in {language_name}."

    response = await client.chat.completions.create(
        model=settings.generation_model,
        messages=[
            {"role": "system", "content": GENERAL_PROMPT + "\n" + lang_instruction},
            {"role": "user", "content": query},
        ],
        max_tokens=settings.max_gen_tokens,
        temperature=0.7,
        stream=True,
    )
    
    async for chunk in response:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
