from wikiwiki.index import BookResult, PageMatch
from wikiwiki.llama import _context, _prompt


def test_context_contains_source_metadata():
    results = [BookResult("A Book", "An Author", (PageMatch(12, "Chapter 2", "useful text", 0.9),))]

    context = _context(results)

    assert "[S1] A Book — Chapter 2 — page 12" in context
    assert "useful text" in context


def test_prompt_includes_previous_conversation():
    results = [BookResult("A Book", "An Author", (PageMatch(12, "Chapter 2", "useful text", 0.9),))]

    prompt = _prompt("What follows?", results, [("What came before?", "An earlier answer.")])

    assert "What came before?" in prompt
    assert "An earlier answer." in prompt
    assert "What follows?" in prompt
