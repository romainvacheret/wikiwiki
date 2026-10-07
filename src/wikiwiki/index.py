from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .calibre import Book, books


SEMANTIC_WEIGHT = 0.7
KEYWORD_WEIGHT = 0.3
RRF_K = 60


@dataclass(frozen=True)
class PageMatch:
    page: int
    chapter: str
    snippet: str
    score: float


@dataclass(frozen=True)
class BookResult:
    title: str
    authors: str
    pages: tuple[PageMatch, ...]


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
CREATE TABLE IF NOT EXISTS chunk_metadata (
    rowid INTEGER PRIMARY KEY,
    chapter TEXT NOT NULL
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
        toc = document.get_toc(simple=True)
        chapters = [
            (entry[2], entry[1])
            for entry in toc
            if len(entry) >= 3 and entry[0] <= 2 and entry[2] > 0
        ]
        for page_number, page in enumerate(document, start=1):
            text = page.get_text("text").strip()
            if text:
                chapter = "Unknown chapter"
                for chapter_page, title in chapters:
                    if chapter_page <= page_number:
                        chapter = title
                    else:
                        break
                yield page_number, chapter, text
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
            metadata_exists = db.execute(
                "SELECT 1 FROM chunk_metadata m JOIN chunks c ON c.rowid = m.rowid WHERE c.book_id = ? LIMIT 1",
                (str(book.calibre_id),),
            ).fetchone()
            if old and old[0] == current and metadata_exists:
                count += 1
                continue
            db.execute(
                "DELETE FROM chunk_metadata WHERE rowid IN (SELECT rowid FROM chunks WHERE book_id = ?)",
                (str(book.calibre_id),),
            )
            db.execute("DELETE FROM chunks WHERE book_id = ?", (str(book.calibre_id),))
            db.execute("DELETE FROM vectors WHERE book_id = ?", (book.calibre_id,))
            db.execute("DELETE FROM documents WHERE book_id = ?", (book.calibre_id,))
            db.execute(
                "INSERT INTO documents VALUES (?, ?, ?, ?, ?)",
                (book.calibre_id, book.title, book.authors, str(book.pdf_path), current),
            )
            pages = list(extract_pages(book.pdf_path))
            vectors = encode([text for _, _, text in pages]) if encode else []
            for position, (page, chapter, text) in enumerate(pages):
                db.execute(
                    "INSERT INTO chunks(text, title, authors, path, page, book_id) VALUES (?, ?, ?, ?, ?, ?)",
                    (text, book.title, book.authors, str(book.pdf_path), page, str(book.calibre_id)),
                )
                chunk_rowid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
                db.execute("INSERT INTO chunk_metadata(rowid, chapter) VALUES (?, ?)", (chunk_rowid, chapter))
                if vectors:
                    db.execute(
                        "INSERT INTO vectors(rowid, book_id, vector) VALUES (?, ?, ?)",
                        (chunk_rowid, book.calibre_id, vectors[position]),
                    )
            count += 1
        db.commit()
    finally:
        db.close()
    return count


def _snippet(text: str, maximum: int = 240) -> str:
    compact = " ".join(text.split())
    if len(compact) <= maximum:
        return compact
    return compact[: maximum - 1].rsplit(" ", 1)[0] + "…"


def _book_results(
    rows: list[tuple[str, str, int, str, str, float]],
    limit: int,
    pages_per_book: int,
) -> list[BookResult]:
    grouped: dict[tuple[str, str], list[PageMatch]] = {}
    for title, authors, page, chapter, text, score in rows:
        key = (title, authors)
        grouped.setdefault(key, []).append(PageMatch(page, chapter, _snippet(text), score))
    ranked = sorted(
        grouped.items(),
        key=lambda item: (-max(match.score for match in item[1]), item[0][0].lower()),
    )[:limit]
    return [
        BookResult(
            title,
            authors,
            tuple(sorted(matches, key=lambda match: -match.score)[:pages_per_book]),
        )
        for (title, authors), matches in ranked
    ]


def search(index_path: Path, topic: str, limit: int = 10, pages_per_book: int = 3) -> list[BookResult]:
    db = sqlite3.connect(index_path)
    try:
        lexical_rows = db.execute(
            """
            SELECT chunks.rowid, chunks.title, chunks.authors, chunks.page,
                   metadata.chapter, chunks.text, bm25(chunks) AS rank
            FROM chunks
            JOIN chunk_metadata metadata ON metadata.rowid = chunks.rowid
            WHERE chunks MATCH ?
            ORDER BY rank, chunks.title COLLATE NOCASE
            """,
            (topic,),
        ).fetchall()
        vector_count = db.execute("SELECT COUNT(*) FROM vectors").fetchone()[0]
        if vector_count:
            try:
                from .embeddings import cosine, query

                topic_vector = query(topic)
                semantic_rows = db.execute(
                    """
                    SELECT c.rowid, c.title, c.authors, c.page, metadata.chapter, c.text, cosine_vector.vector
                    FROM chunks c
                    JOIN chunk_metadata metadata ON metadata.rowid = c.rowid
                    JOIN vectors cosine_vector ON cosine_vector.rowid = c.rowid
                    """
                ).fetchall()
                semantic_scores = {
                    row[0]: cosine(row[6], topic_vector)
                    for row in semantic_rows
                }
                semantic_rank = {
                    rowid: rank
                    for rank, (rowid, _) in enumerate(
                        sorted(semantic_scores.items(), key=lambda item: -item[1]),
                        start=1,
                    )
                }
                keyword_rank = {
                    row[0]: rank for rank, row in enumerate(lexical_rows, start=1)
                }
                row_by_id = {row[0]: row for row in semantic_rows}
                for row in lexical_rows:
                    row_by_id.setdefault(row[0], row)

                combined = []
                for rowid, row in row_by_id.items():
                    score = 0.0
                    if rowid in semantic_rank:
                        score += SEMANTIC_WEIGHT / (RRF_K + semantic_rank[rowid])
                    if rowid in keyword_rank:
                        score += KEYWORD_WEIGHT / (RRF_K + keyword_rank[rowid])
                    if rowid in semantic_scores:
                        title, authors, page, chapter, text = row[1:6]
                    else:
                        _, title, authors, page, chapter, text, _ = row
                    combined.append((title, authors, page, chapter, text, score))
                combined.sort(key=lambda row: (-row[5], row[0].lower()))
                return _book_results(combined, limit, pages_per_book)
            except (ImportError, ModuleNotFoundError):
                pass
    finally:
        db.close()

    return _book_results(
        [(title, authors, page, chapter, text, -rank) for _, title, authors, page, chapter, text, rank in lexical_rows],
        limit,
        pages_per_book,
    )
