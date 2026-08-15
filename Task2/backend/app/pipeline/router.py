"""
Routing logic to choose between RAG, WEB, GENERAL_LLM, and RAG_PLUS_WEB.
"""
import re
from typing import TypedDict
from groq import AsyncGroq
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings

class RouteDecision(TypedDict):
    route: str
    reason: str
    needs_current_info: bool

_client: AsyncGroq | None = None

def get_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=settings.groq_api_key)
    return _client

# Heuristics for fast routing without LLM
WEB_KEYWORDS = ["latest", "today", "current", "recent", "news", "weather", "live", "schedule", "price", "aj ka", "aaj", "aaj ka", "update"]
GENERAL_KEYWORDS = ["write", "code", "python", "script", "explain", "brainstorm", "summarize", "how to write", "translate"]

def _heuristic_route(query: str) -> RouteDecision | None:
    query_lower = query.lower()
    
    # 1. Check for web keywords
    for w in WEB_KEYWORDS:
        if re.search(r'\b' + w + r'\b', query_lower):
            return {"route": "WEB", "reason": f"Matched web keyword: {w}", "needs_current_info": True}
            
    # 2. Check for general coding/writing
    for w in GENERAL_KEYWORDS:
        if re.search(r'\b' + w + r'\b', query_lower):
            return {"route": "GENERAL_LLM", "reason": f"Matched general keyword: {w}", "needs_current_info": False}
            
    return None


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=0.3, min=0.3, max=1.0),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def _llm_route(query: str) -> RouteDecision:
    """Fallback to LLM routing if heuristics fail."""
    client = get_client()
    
    system_prompt = """You are a query router. Analyze the user's query and route it to one of these systems:
- RAG: For factual questions likely answerable by a historical or fixed dataset (e.g. History, ancient wisdom, fixed facts, specific indexed knowledge).
- WEB: For queries requiring current, real-time, or latest information (news, weather, sports scores).
- GENERAL_LLM: For creative writing, coding, brainstorming, translations, or general conversation.
- RAG_PLUS_WEB: If it needs BOTH historical dataset knowledge AND current web information.

Respond ONLY with the route name."""

    response = await client.chat.completions.create(
        model=settings.generation_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Query: {query}\n\nRoute:"},
        ],
        max_tokens=10,
        temperature=0.0,
    )

    answer = (response.choices[0].message.content or "").strip().upper()
    
    valid_routes = ["RAG", "WEB", "GENERAL_LLM", "RAG_PLUS_WEB"]
    for vr in valid_routes:
        if vr in answer:
            return {"route": vr, "reason": "LLM classification", "needs_current_info": ("WEB" in vr)}
            
    return {"route": "RAG", "reason": "Default fallback", "needs_current_info": False}


async def route_query(query: str) -> RouteDecision:
    """Determine the optimal route for the query."""
    if not query.strip():
        return {"route": "GENERAL_LLM", "reason": "Empty query", "needs_current_info": False}
        
    decision = _heuristic_route(query)
    if decision:
        return decision
        
    try:
        return await _llm_route(query)
    except Exception as e:
        print(f"Routing LLM failed: {e}")
        return {"route": "RAG", "reason": "LLM failed, fallback to RAG", "needs_current_info": False}
