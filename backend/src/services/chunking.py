"""Splits raw document text into overlapping chunks sized for embedding.

Why RecursiveCharacterTextSplitter and not a naive fixed-size split: it tries
paragraph breaks first, then sentences, then words, before falling back to a
hard character cut — so chunks stay on natural boundaries far more often.
That matters for retrieval quality: a chunk that ends mid-sentence embeds
(and later matches a question) worse than one that ends on a paragraph
boundary.

Why character length and not token count: it's a close enough proxy at this
chunk size, and avoids pulling in a tokenizer just for chunking. Token-based
sizing would matter more if we were packing chunks close to an LLM context
limit — we're not; these chunks just need to be small enough to embed well
and large enough to retain context.
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.core.config import get_settings


def chunk_text(text: str) -> list[str]:
    settings = get_settings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        length_function=len,
    )
    chunks = splitter.split_text(text)
    # Drop whitespace-only fragments (blank pages, trailing newlines) so we
    # never embed and store an empty chunk.
    return [chunk.strip() for chunk in chunks if chunk.strip()]
