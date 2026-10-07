from wikiwiki.index import (
    BookResult,
    IndexedChunk,
    PageMatch,
    RankedChunk,
    _book_results,
    _snippet,
)


def test_snippet_collapses_whitespace_and_truncates():
    assert _snippet("one\n two\tthree") == "one two three"
    assert _snippet("abcdefgh", maximum=6) == "abcde…"


def test_book_results_groups_pages_and_limits_books():
    rows = [
        RankedChunk(IndexedChunk(1, "Book A", "Author A", 2, "Chapter 1", "second"), 0.8),
        RankedChunk(IndexedChunk(2, "Book A", "Author A", 1, "Chapter 1", "first"), 0.9),
        RankedChunk(IndexedChunk(3, "Book B", "Author B", 3, "Chapter 2", "other"), 0.7),
    ]

    results = _book_results(rows, limit=1, pages_per_book=1)

    assert results == [
        BookResult("Book A", "Author A", (PageMatch(1, "Chapter 1", "first", 0.9),))
    ]
