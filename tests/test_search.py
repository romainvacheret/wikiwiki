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
    rows = db.execute("SELECT rowid, page FROM chunks ORDER BY rowid").fetchall()
    db.executemany(
        "INSERT INTO chunk_metadata(rowid, chapter) VALUES (?, ?)",
        [(rowid, "Chapter 1" if page == 1 else "Chapter 2") for rowid, page in rows],
    )
    db.commit()
    db.close()

    results = search(path, "event sourcing")
    assert [(result.title, result.authors) for result in results] == [("Event Book", "A")]
    assert [match.page for match in results[0].pages] == [1, 2]
    assert [match.chapter for match in results[0].pages] == ["Chapter 1", "Chapter 2"]
