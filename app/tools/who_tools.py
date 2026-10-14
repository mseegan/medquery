import httpx
from anthropic import Anthropic
from langchain_core.tools import tool

from app.config import settings

GHO_ENDPOINT = "https://ghoapi.azureedge.net/api"
MAX_GHO_RESULTS = 10

_anthropic_client = Anthropic(api_key=settings.anthropic_api_key)


@tool
def who_gho_lookup(indicator_code: str, country_code: str | None = None) -> str:
    """Look up a WHO Global Health Observatory (GHO) statistical indicator,
    e.g. indicator_code='WHOSIS_000001' for life expectancy at birth.
    country_code is an optional ISO3 code, e.g. 'KEN' for Kenya, to filter
    results to one country."""
    url = f"{GHO_ENDPOINT}/{indicator_code}"
    params = {}
    if country_code:
        params["$filter"] = f"SpatialDim eq '{country_code.upper()}'"

    try:
        response = httpx.get(url, params=params, timeout=8.0)
        response.raise_for_status()
    except httpx.HTTPError:
        try:
            response = httpx.get(url, params=params, timeout=8.0)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return f"Error: WHO GHO lookup failed ({exc}). Check the indicator_code."

    data = response.json()
    values = data.get("value", [])
    if not values:
        return f"No WHO GHO data found for indicator '{indicator_code}'" + (
            f" and country '{country_code}'." if country_code else "."
        )

    lines = []
    for entry in values[:MAX_GHO_RESULTS]:
        lines.append(
            f"{entry.get('SpatialDim')} | {entry.get('TimeDim')} | {entry.get('NumericValue')}"
        )
    return "\n".join(lines)


WHO_FACT_SHEET_SEARCH_TOOL_SPEC = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": 3,
    "allowed_domains": ["who.int"],
}


@tool
def who_fact_sheet_search(query: str) -> str:
    """Search WHO (who.int) fact sheets and official pages for clinical
    guidance/background on a disease, condition, or health topic. Use this
    for narrative WHO guidance that isn't a plain statistical indicator."""
    try:
        response = _anthropic_client.messages.create(
            model=settings.sonnet_model,
            max_tokens=1024,
            tools=[WHO_FACT_SHEET_SEARCH_TOOL_SPEC],
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Search who.int for information on: {query}. "
                        "Summarize the key points in 3-5 sentences."
                    ),
                }
            ],
        )
    except Exception as exc:  # anthropic SDK error types vary by failure mode
        return f"Error: WHO fact sheet search failed ({exc})."

    text_parts = []
    sources = []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            text_parts.append(block.text)
            for citation in getattr(block, "citations", None) or []:
                url = getattr(citation, "url", None)
                title = getattr(citation, "title", None)
                if url:
                    sources.append(f"{title or url} ({url})")

    summary = "\n".join(text_parts).strip()
    if not summary:
        return f"No WHO fact sheet results found for '{query}'."

    if sources:
        unique_sources = list(dict.fromkeys(sources))
        summary += "\n\nSources:\n" + "\n".join(unique_sources)
    return summary


WHO_TOOLS = [who_gho_lookup, who_fact_sheet_search]
