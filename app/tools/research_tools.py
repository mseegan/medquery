from langchain_core.tools import tool

from app.research.chain import research_chain


@tool
def research_disease(disease: str, focus: str = "treatment") -> str:
    """Research a disease or condition and return a short summary with numbered
    citations, drawn from MedlinePlus, recent PubMed review articles (last three
    years), and WHO guidance. focus is a short keyword such as treatment,
    diagnosis, prevention, or causes."""
    try:
        return research_chain.invoke({"disease": disease.strip(), "focus": focus.strip() or "treatment"})
    except Exception as exc:
        return f"Error: disease research is unavailable right now ({exc})."
