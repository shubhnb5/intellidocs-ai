from src.services.chunking import chunk_text


def test_chunk_text_splits_long_text_into_multiple_chunks():
    text = "Sentence one. " * 200
    chunks = chunk_text(text)
    assert len(chunks) > 1
    assert all(chunk.strip() for chunk in chunks)


def test_chunk_text_returns_single_chunk_for_short_text():
    chunks = chunk_text("A short paragraph that fits in one chunk.")
    assert len(chunks) == 1


def test_chunk_text_drops_whitespace_only_input():
    assert chunk_text("   \n\n   ") == []
