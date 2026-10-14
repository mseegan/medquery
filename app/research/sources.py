"""Medical reference sources for disease research. Each returns LangChain
Documents (text plus title/url metadata) and returns an empty list if the
source can't be reached."""
import html
import re
import xml.etree.ElementTree as ET
import httpx
from anthropic import Anthropic
from langchain_core.documents import Document

from app.config import settings

MEDLINEPLUS_URL = "https://wsearch.nlm.nih.gov/ws/query"
PUBMED_SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
PUBMED_ARTICLE_URL = "https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
TIMEOUT = 10.0
PUBMED_LOOKBACK_DAYS = 3 * 365
WHO_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": 3,
    "allowed_domains": ["who.int"],
}


def _strip_tags(text: str | None) -> str:
    if not text:
        return ""
    return html.unescape(re.sub(r"<[^<]+?>", "", text)).strip()


def medlineplus_docs(disease: str, limit: int = 3) -> list[Document]:
    """Consumer health topics from MedlinePlus."""
    try:
        response = httpx.get(
            MEDLINEPLUS_URL,
            params={"db": "healthTopics", "term": disease, "retmax": limit},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        root = ET.fromstring(response.text)
    except (httpx.HTTPError, ET.ParseError):
        return []

    docs = []
    for document in root.findall(".//document")[:limit]:
        fields = {c.get("name"): c.text for c in document.findall("content")}
        title = _strip_tags(fields.get("title"))
        text = _strip_tags(fields.get("FullSummary") or fields.get("snippet"))
        if title and text:
            docs.append(
                Document(
                    page_content=f"{title}. {text}",
                    metadata={"source": "MedlinePlus", "title": title, "url": document.get("url", "")},
                )
            )
    return docs


def _element_text(element: ET.Element | None) -> str:
    return "".join(element.itertext()).strip() if element is not None else ""


def _pubmed_article(article: ET.Element) -> Document | None:
    pmid = article.findtext(".//PMID")
    title = _element_text(article.find(".//ArticleTitle"))
    abstract = " ".join(_element_text(part) for part in article.findall(".//AbstractText"))
    if not (pmid and title and abstract):
        return None
    journal = article.findtext(".//Journal/Title") or ""
    year = article.findtext(".//JournalIssue/PubDate/Year") or article.findtext(".//PubDate/MedlineDate") or ""
    return Document(
        page_content=f"{title}. {abstract}",
        metadata={
            "source": "PubMed",
            "title": f"{title} ({journal}, {year})".strip(),
            "url": PUBMED_ARTICLE_URL.format(pmid=pmid),
        },
    )


def pubmed_docs(disease: str, focus: str, limit: int = 4) -> list[Document]:
    """Recent review articles (last three years) from PubMed/MEDLINE."""
    try:
        search = httpx.get(
            PUBMED_SEARCH_URL,
            params={
                "db": "pubmed",
                "term": f"({disease}) AND ({focus}) AND review[pt]",
                "datetype": "pdat",
                "reldate": PUBMED_LOOKBACK_DAYS,
                "retmax": limit,
                "retmode": "json",
                "sort": "relevance",
            },
            timeout=TIMEOUT,
        )
        search.raise_for_status()
        ids = search.json()["esearchresult"]["idlist"]
        if not ids:
            return []
        fetch = httpx.get(
            PUBMED_FETCH_URL,
            params={"db": "pubmed", "id": ",".join(ids), "retmode": "xml"},
            timeout=TIMEOUT,
        )
        fetch.raise_for_status()
        root = ET.fromstring(fetch.text)
    except (httpx.HTTPError, ET.ParseError, KeyError, ValueError):
        return []

    docs = (_pubmed_article(a) for a in root.findall(".//PubmedArticle"))
    return [d for d in docs if d]


def who_docs(disease: str, focus: str) -> list[Document]:
    """WHO guidance, found with Claude's web search restricted to who.int."""
    try:
        client = Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=settings.sonnet_model,
            max_tokens=1024,
            tools=[WHO_SEARCH_TOOL],
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Search who.int for WHO guidance on {focus} of {disease}. "
                        "Summarize the key points in 3-5 sentences."
                    ),
                }
            ],
        )
    except Exception:  # SDK error types vary by failure mode
        return []

    text, urls = [], []
    for block in response.content:
        if getattr(block, "type", None) == "text":
            text.append(block.text)
            urls += [c.url for c in (getattr(block, "citations", None) or []) if getattr(c, "url", None)]
    summary = " ".join(text).strip()
    if not summary:
        return []
    return [
        Document(
            page_content=summary,
            metadata={
                "source": "WHO",
                "title": "WHO guidance",
                "url": urls[0] if urls else "https://www.who.int",
            },
        )
    ]
