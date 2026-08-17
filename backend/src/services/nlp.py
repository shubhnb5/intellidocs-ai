"""Classical NLP pipeline run once per uploaded document: named entity
recognition and keyphrase extraction via spaCy, and extractive summarization
via TextRank over sentence embeddings.

Deliberately not another LLM call. This is the "NLP" half of the project,
distinct from the "LLM/Agents" half in services/llm.py and services/rag.py —
same document, three different, independently explainable techniques.
"""

from functools import lru_cache

import spacy
from pydantic import BaseModel

from src.core.config import get_settings
from src.services.embeddings import get_embedding_service

# Numeric entity types (dates, percentages, quantities...) are usually noise
# for a "what/who is this document about" signal — worth excluding rather
# than showing "37%" and "Q3" next to actual people and organizations.
_EXCLUDED_ENTITY_LABELS = {"CARDINAL", "ORDINAL", "PERCENT", "QUANTITY", "TIME"}


class Entity(BaseModel):
    text: str
    label: str


class NlpResult(BaseModel):
    entities: list[Entity]
    topics: list[str]
    summary: str


@lru_cache
def _get_nlp():
    """Cached: loading the spaCy pipeline is the expensive part, so do it
    once per process. Requires `python -m spacy download en_core_web_sm`
    to have been run first — see backend/.env.example."""
    return spacy.load("en_core_web_sm")


def _extract_entities(doc) -> list[Entity]:
    seen: set[tuple[str, str]] = set()
    entities: list[Entity] = []
    for ent in doc.ents:
        if ent.label_ in _EXCLUDED_ENTITY_LABELS:
            continue
        key = (ent.text.strip().lower(), ent.label_)
        if key in seen:
            continue
        seen.add(key)
        entities.append(Entity(text=ent.text.strip(), label=ent.label_))
    return entities


def _extract_topics(doc, *, top_n: int = 10) -> list[str]:
    """Frequency-ranked noun phrases: a simple, explainable keyphrase
    extractor. Trade-off worth naming: it ranks by frequency *within this
    document only*, so it won't downweight generic phrases the way TF-IDF
    across a whole corpus would. Good enough for a single-document "what is
    this about" signal; see ARCHITECTURE.md for the corpus-aware upgrade
    path.
    """
    counts: dict[str, int] = {}
    for chunk in doc.noun_chunks:
        phrase = " ".join(
            token.lemma_.lower() for token in chunk if token.is_alpha and not token.is_stop
        ).strip()
        if len(phrase) < 3:
            continue
        counts[phrase] = counts.get(phrase, 0) + 1

    ranked = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return [phrase for phrase, _count in ranked[:top_n]]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _text_rank(
    vectors: list[list[float]], *, damping: float = 0.85, iterations: int = 30
) -> list[float]:
    """TextRank (Mihalcea & Tarau, 2004): sentences are nodes in a graph,
    edges weighted by embedding cosine similarity, importance scored by
    running PageRank on that similarity graph. A sentence scores highly when
    it's similar to many other sentences — i.e. representative of the
    document as a whole, not just long or first.
    """
    n = len(vectors)
    similarity = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                similarity[i][j] = _cosine_similarity(vectors[i], vectors[j])

    # Row-normalize so each sentence's outgoing edge weights sum to 1 —
    # the standard PageRank transition-matrix setup.
    row_sums = [sum(row) or 1.0 for row in similarity]
    transition = [[w / row_sums[i] for w in row] for i, row in enumerate(similarity)]

    scores = [1.0 / n] * n
    for _ in range(iterations):
        scores = [
            (1 - damping) / n + damping * sum(transition[j][i] * scores[j] for j in range(n))
            for i in range(n)
        ]
    return scores


def _summarize(doc, *, sentence_count: int = 4) -> str:
    sentences = [s.text.strip() for s in doc.sents if len(s.text.strip()) > 20]
    if not sentences:
        return ""
    if len(sentences) <= sentence_count:
        return " ".join(sentences)

    # Cap how many sentences get embedded/ranked — long documents don't need
    # a denser similarity graph, just a representative sample of one.
    sentences = sentences[:200]

    vectors = get_embedding_service().embed(sentences)
    scores = _text_rank(vectors)

    top_indices = sorted(range(len(sentences)), key=lambda i: scores[i], reverse=True)
    top_indices = top_indices[:sentence_count]
    top_indices.sort()  # restore original reading order for a coherent summary

    return " ".join(sentences[i] for i in top_indices)


def analyze_document(text: str) -> NlpResult:
    settings = get_settings()
    nlp = _get_nlp()
    doc = nlp(text[: settings.nlp_max_chars])

    return NlpResult(
        entities=_extract_entities(doc),
        topics=_extract_topics(doc),
        summary=_summarize(doc),
    )
