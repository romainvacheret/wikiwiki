from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from .calibre import Book, books


SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    book_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    authors TEXT NOT NULL,
    path TEXT NOT NULL,
    fingerprint TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS vectors (
    rowid INTEGER PRIMARY KEY,
    book_id INTEGER NOT NULL,
    vector BLOB NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(
    text, title, authors, path UNINDEXED, page UNINDEXED, book_id UNINDEXED
);
"""


def fingerprint(path: Path) -> str:
    stat = path.stat()
    return hashlib.sha256(f"{path}:{stat.st_size}:{stat.st_mtime_ns}".encode()).hexdigest()


def extract_pages(path: Path):
    import pymupdf

    document = pymupdf.open(path)
    try:
        for page_number, page in enumerate(document, start=1):
            text = page.get_text("text").strip()
            if text:
                yield page_number, text
    finally:
        document.close()


def rebuild(library: Path, index_path: Path) -> int:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(index_path)
    db.executescript(SCHEMA)
    count = 0
    try:
        try:
            from .embeddings import encode
        except ImportError:
            encode = None
        for book in books(library):
            current = fingerprint(book.pdf_path)
            old = db.execute("SELECT fingerprint FROM documents WHERE book_id = ?", (book.calibre_id,)).fetchone()
            if old and old[0] == current:
                count += 1
                continue
            db.execute("DELETE FROM chunks WHERE book_id = ?", (str(book.calibre_id),))
            db.execute("DELETE FROM vectors WHERE book_id = ?", (book.calibre_id,))
            db.execute("DELETE FROM documents WHERE book_id = ?", (book.calibre_id,))
            db.execute(
                "INSERT INTO documents VALUES (?, ?, ?, ?, ?)",
                (book.calibre_id, book.title, book.authors, str(book.pdf_path), current),
            )
            pages = list(extract_pages(book.pdf_path))
            vectors = encode([text for _, text in pages]) if encode else []
            for position, (page, text) in enumerate(pages):
                db.execute(
                    "INSERT INTO chunks(text, title, authors, path, page, book_id) VALUES (?, ?, ?, ?, ?, ?)",
                    (text, book.title, book.authors, str(book.pdf_path), page, str(book.calibre_id)),
                )
                if vectors:
                    db.execute(
                        "INSERT INTO vectors(rowid, book_id, vector) VALUES (?, ?, ?)",
                        (db.execute("SELECT last_insert_rowid()").fetchone()[0], book.calibre_id, vectors[position]),
                    )
            count += 1
        db.commit()
    finally:
        db.close()
    return count


def search(index_path: Path, topic: str, limit: int = 10) -> list[tuple[str, str]]:
    db = sqlite3.connect(index_path)
    try:
        try:
            from .embeddings import cosine, query
            topic_vector = query(topic)
            semantic_rows = db.execute(
                "SELECT d.title, d.authors, v.vector FROM vectors v JOIN documents d ON d.book_id = v.book_id"
            ).fetchall()
            if semantic_rows:
                scores: dict[tuple[str, str], float] = {}
                for title, authors, vector in semantic_rows:
                    key = (title, authors)
                    scores[key] = max(scores.get(key, -1.0), cosine(vector, topic_vector))
                return [key for key, _ in sorted(scores.items(), key=lambda item: (-item[1], item[0][0].lower()))[:limit]]
        except (ImportError, ModuleNotFoundError):
            pass
        rows = db.execute(
            """
            SELECT title, authors, COUNT(*) AS hits
            FROM chunks
            WHERE chunks MATCH ?
            GROUP BY book_id, title, authors
            ORDER BY hits DESC, title COLLATE NOCASE
            LIMIT ?
            """,
            (topic, limit),
        ).fetchall()
    finally:
        db.close()
    return [(title, authors) for title, authors, _ in rows]
