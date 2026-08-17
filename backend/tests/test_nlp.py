"""Tests the math underneath the NLP pipeline (cosine similarity, TextRank)
directly on plain vectors — no spaCy model load required, so these run
without the `spacy download` step CI/local setup needs for the full
pipeline. See test_documents.py for the route-level test with NLP faked out.
"""

from src.services.nlp import _cosine_similarity, _text_rank


def test_cosine_similarity_of_identical_vectors_is_one():
    assert _cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_cosine_similarity_of_orthogonal_vectors_is_zero():
    assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0


def test_cosine_similarity_handles_zero_vector():
    assert _cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_text_rank_scores_sum_to_roughly_one():
    # PageRank scores over a fully-connected graph form a probability
    # distribution — they should sum to ~1 regardless of the input vectors.
    vectors = [[1.0, 0.0], [0.9, 0.1], [0.0, 1.0]]
    scores = _text_rank(vectors, iterations=20)

    assert len(scores) == 3
    assert abs(sum(scores) - 1.0) < 1e-6


def test_text_rank_favors_the_more_central_sentence():
    # Sentence 0 is similar to both 1 and 2; 1 and 2 are dissimilar to each
    # other. TextRank should rank the "hub" sentence highest.
    vectors = [
        [1.0, 1.0],  # similar to both of the below
        [1.0, 0.0],
        [0.0, 1.0],
    ]
    scores = _text_rank(vectors, iterations=30)

    assert scores[0] > scores[1]
    assert scores[0] > scores[2]
