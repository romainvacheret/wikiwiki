import sqlite3

from wikiwiki.index import SCHEMA, search


def test_search_ranks_books_by_matching_pages(tmp_path):
    path = tmp_path / "index.sqlite3"
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    db.executemany(
        "INSERT INTO chunks(text, title, authors, path, page, book_id) VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("event sourcing stores events", "Event Book", "A", "a.pdf", 1, "1"),
            ("event sourcing and projections", "Event Book", "A", "a.pdf", 2, "1"),
            ("cooking recipes", "Cooking Book", "B", "b.pdf", 1, "2"),
        ],
    )
    db.commit()
    db.close()

    assert search(path, "event sourcing") == [("Event Book", "A")]

