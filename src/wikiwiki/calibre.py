from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Book:
    calibre_id: int
    title: str
    authors: str
    pdf_path: Path


def books(library: Path) -> list[Book]:
    db = sqlite3.connect(library / "metadata.db")
    db.row_factory = sqlite3.Row
    try:
        rows = db.execute(
            """
            SELECT b.id, b.title,
                   COALESCE(GROUP_CONCAT(a.name, ', '), '') AS authors,
                   b.path AS relative_path,
                   d.name AS filename
            FROM books b
            LEFT JOIN books_authors_link bal ON bal.book = b.id
            LEFT JOIN authors a ON a.id = bal.author
            JOIN data d ON d.book = b.id AND lower(d.format) = 'pdf'
            GROUP BY b.id, b.title, b.path, d.name
            ORDER BY b.title COLLATE NOCASE
            """
        ).fetchall()
    finally:
        db.close()

    result = []
    for row in rows:
        pdf_path = library / row["relative_path"] / f"{row['filename']}.pdf"
        if pdf_path.exists():
            result.append(Book(row["id"], row["title"], row["authors"], pdf_path))
    return result
