import html
import re
import xml.etree.ElementTree as ET

import httpx
from langchain_core.tools import tool

MEDLINEPLUS_ENDPOINT = "https://wsearch.nlm.nih.gov/ws/query"
MAX_RESULTS = 5


def _strip_tags(text: str | None) -> str:
    if not text:
        return ""
    return html.unescape(re.sub(r"<[^<]+?>", "", text)).strip()


@tool
def medlineplus_search(query: str) -> str:
    """Search MedlinePlus health topics for consumer/clinical reference
    information via the official MedlinePlus Web Service API. Returns
    title, snippet, and source URL for the top matching topics."""
    params = {"db": "healthTopics", "term": query, "retmax": MAX_RESULTS}
    try:
        response = httpx.get(MEDLINEPLUS_ENDPOINT, params=params, timeout=8.0)
        response.raise_for_status()
    except httpx.HTTPError:
        try:
            response = httpx.get(MEDLINEPLUS_ENDPOINT, params=params, timeout=8.0)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return f"Error: MedlinePlus lookup failed ({exc})."

    try:
        root = ET.fromstring(response.text)
    except ET.ParseError as exc:
        return f"Error: could not parse MedlinePlus response ({exc})."

    results = []
    for document in root.findall(".//document")[:MAX_RESULTS]:
        url = document.get("url", "")
        fields = {c.get("name"): c.text for c in document.findall("content")}
        title = _strip_tags(fields.get("title"))
        snippet = _strip_tags(fields.get("snippet") or fields.get("FullSummary"))
        if title:
            results.append(f"{title}\n{snippet}\nSource: {url}")

    if not results:
        return f"No MedlinePlus results found for '{query}'."
    return "\n\n".join(results)
