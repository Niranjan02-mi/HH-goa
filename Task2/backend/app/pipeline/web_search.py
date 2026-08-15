"""
Web search provider abstraction (Tavily).
"""
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings
from app.utils.latency import timed_ms

@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=2.0),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
    reraise=True,
)
async def perform_web_search(query: str, max_results: int = 5) -> tuple[list[dict], float]:
    """
    Search the web using Tavily.
    Returns a tuple of (results, latency_ms).
    """
    if not settings.web_search_api_key or settings.web_search_provider.lower() != "tavily":
        return [], 0.0

    url = "https://api.tavily.com/search"
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "api_key": settings.web_search_api_key,
        "query": query,
        "search_depth": "basic",
        "include_answer": False,
        "include_images": False,
        "include_raw_content": False,
        "max_results": max_results
    }

    with timed_ms() as timing:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

    results = []
    for res in data.get("results", []):
        results.append({
            "title": res.get("title", ""),
            "url": res.get("url", ""),
            "snippet": res.get("content", ""),
            "published_at": res.get("published_date", "")
        })

    return results, timing["ms"]
