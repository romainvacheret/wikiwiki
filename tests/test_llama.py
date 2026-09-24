from wikiwiki.index import BookResult, PageMatch
from wikiwiki.llama import _context


def test_context_contains_source_metadata():
    results = [BookResult("A Book", "An Author", (PageMatch(12, "Chapter 2", "useful text", 0.9),))]

    context = _context(results)

    assert "[S1] A Book — Chapter 2 — page 12" in context
    assert "useful text" in context
