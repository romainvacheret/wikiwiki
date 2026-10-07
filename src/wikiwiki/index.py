from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .calibre import Book, books
from .embeddings import cosine, encode, query
from .pdf import ExtractedPage, extract_pages


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


@dataclass(frozen=True)
class IndexedChunk:
    rowid: int
    title: str
    authors: str
    page: int
    chapter: str
    text: str


@dataclass(frozen=True)
class RankedChunk:
    chunk: IndexedChunk
    score: float


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


def connect(index_path: Path) -> sqlite3.Connection:
    index_path.parent.mkdir(parents=True, exist_ok=True)
    database = sqlite3.connect(index_path)
    database.executescript(SCHEMA)
    return database


def fingerprint(path: Path) -> str:
    stat = path.stat()
    value = f"{path}:{stat.st_size}:{stat.st_mtime_ns}"
    return hashlib.sha256(value.encode()).hexdigest()


def _has_metadata(database: sqlite3.Connection, book_id: int) -> bool:
    row = database.execute(
        "SELECT 1 FROM chunk_metadata m JOIN chunks c ON c.rowid = m.rowid "
        "WHERE c.book_id = ? LIMIT 1",
        (str(book_id),),
    ).fetchone()
    return row is not None


def _has_vectors(database: sqlite3.Connection, book_id: int) -> bool:
    row = database.execute(
        "SELECT 1 FROM vectors WHERE book_id = ? LIMIT 1",
        (book_id,),
    ).fetchone()
    return row is not None


def _needs_reindex(
    database: sqlite3.Connection,
    book: Book,
    current_fingerprint: str,
) -> bool:
    row = database.execute(
        "SELECT fingerprint FROM documents WHERE book_id = ?",
        (book.calibre_id,),
    ).fetchone()
    return not (
        row
        and row[0] == current_fingerprint
        and _has_metadata(database, book.calibre_id)
        and _has_vectors(database, book.calibre_id)
    )


def _clear_book(database: sqlite3.Connection, book_id: int) -> None:
    database.execute(
        "DELETE FROM chunk_metadata WHERE rowid IN "
        "(SELECT rowid FROM chunks WHERE book_id = ?)",
        (str(book_id),),
    )
    database.execute("DELETE FROM chunks WHERE book_id = ?", (str(book_id),))
    database.execute("DELETE FROM vectors WHERE book_id = ?", (book_id,))
    database.execute("DELETE FROM documents WHERE book_id = ?", (book_id,))


def _save_book(
    database: sqlite3.Connection,
    book: Book,
    pages: list[ExtractedPage],
    vectors: list[bytes],
    file_fingerprint: str,
) -> None:
    database.execute(
        "INSERT INTO documents VALUES (?, ?, ?, ?, ?)",
        (book.calibre_id, book.title, book.authors, str(book.pdf_path), file_fingerprint),
    )
    for position, page in enumerate(pages):
        database.execute(
            "INSERT INTO chunks(text, title, authors, path, page, book_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                page.text,
                book.title,
                book.authors,
                str(book.pdf_path),
                page.number,
                str(book.calibre_id),
            ),
        )
        chunk_rowid = database.execute("SELECT last_insert_rowid()").fetchone()[0]
        database.execute(
            "INSERT INTO chunk_metadata(rowid, chapter) VALUES (?, ?)",
            (chunk_rowid, page.chapter),
        )
        if vectors:
            database.execute(
                "INSERT INTO vectors(rowid, book_id, vector) VALUES (?, ?, ?)",
                (chunk_rowid, book.calibre_id, vectors[position]),
            )


def _index_book(
    database: sqlite3.Connection,
    book: Book,
    encoder,
) -> None:
    file_fingerprint = fingerprint(book.pdf_path)
    if not _needs_reindex(database, book, file_fingerprint):
        return

    _clear_book(database, book.calibre_id)
    pages = extract_pages(book.pdf_path)
    vectors = encoder([page.text for page in pages]) if encoder else []
    _save_book(database, book, pages, vectors, file_fingerprint)


def rebuild(library: Path, index_path: Path) -> int:
    database = connect(index_path)
    indexed_books = 0
    try:
        for book in books(library):
            _index_book(database, book, encode)
            indexed_books += 1
        database.commit()
    finally:
        database.close()
    return indexed_books


def _snippet(text: str, maximum: int = 240) -> str:
    compact = " ".join(text.split())
    if len(compact) <= maximum:
        return compact
    return compact[: maximum - 1].rsplit(" ", 1)[0] + "…"


def _load_keyword_matches(
    database: sqlite3.Connection,
    topic: str,
) -> list[tuple[IndexedChunk, float]]:
    rows = database.execute(
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
    return [
        (
            IndexedChunk(rowid, title, authors, page, chapter, text),
            -rank,
        )
        for rowid, title, authors, page, chapter, text, rank in rows
    ]


def _load_semantic_matches(
    database: sqlite3.Connection,
    topic: str,
) -> list[tuple[IndexedChunk, float]]:
    topic_vector = query(topic)
    rows = database.execute(
        """
        SELECT c.rowid, c.title, c.authors, c.page, metadata.chapter,
               c.text, vectors.vector
        FROM chunks c
        JOIN chunk_metadata metadata ON metadata.rowid = c.rowid
        JOIN vectors ON vectors.rowid = c.rowid
        """
    ).fetchall()
    return [
        (
            IndexedChunk(rowid, title, authors, page, chapter, text),
            cosine(vector, topic_vector),
        )
        for rowid, title, authors, page, chapter, text, vector in rows
    ]


def _reciprocal_rank(rank: int) -> float:
    return 1 / (RRF_K + rank)


def _combine_matches(
    semantic_matches: list[tuple[IndexedChunk, float]],
    keyword_matches: list[tuple[IndexedChunk, float]],
) -> list[RankedChunk]:
    semantic_by_id = {chunk.rowid: chunk for chunk, _ in semantic_matches}
    keyword_by_id = {chunk.rowid: chunk for chunk, _ in keyword_matches}
    semantic_rank = {
        chunk.rowid: rank
        for rank, (chunk, _) in enumerate(
            sorted(semantic_matches, key=lambda item: -item[1]),
            start=1,
        )
    }
    keyword_rank = {
        chunk.rowid: rank
        for rank, (chunk, _) in enumerate(keyword_matches, start=1)
    }

    ranked = []
    for rowid in semantic_by_id.keys() | keyword_by_id.keys():
        score = 0.0
        if rowid in semantic_rank:
            score += SEMANTIC_WEIGHT * _reciprocal_rank(semantic_rank[rowid])
        if rowid in keyword_rank:
            score += KEYWORD_WEIGHT * _reciprocal_rank(keyword_rank[rowid])
        chunk = semantic_by_id.get(rowid) or keyword_by_id[rowid]
        ranked.append(RankedChunk(chunk, score))
    return sorted(ranked, key=lambda item: (-item.score, item.chunk.title.lower()))


def _book_results(
    ranked_chunks: list[RankedChunk],
    limit: int,
    pages_per_book: int,
) -> list[BookResult]:
    grouped: dict[tuple[str, str], list[RankedChunk]] = {}
    for ranked in ranked_chunks:
        key = (ranked.chunk.title, ranked.chunk.authors)
        grouped.setdefault(key, []).append(ranked)

    ranked_books = sorted(
        grouped.items(),
        key=lambda item: (-max(page.score for page in item[1]), item[0][0].lower()),
    )[:limit]
    return [
        BookResult(
            title,
            authors,
            tuple(
                PageMatch(
                    page=page.chunk.page,
                    chapter=page.chunk.chapter,
                    snippet=_snippet(page.chunk.text),
                    score=page.score,
                )
                for page in sorted(matches, key=lambda item: -item.score)[:pages_per_book]
            ),
        )
        for (title, authors), matches in ranked_books
    ]


def search(
    index_path: Path,
    topic: str,
    limit: int = 10,
    pages_per_book: int = 3,
) -> list[BookResult]:
    database = connect(index_path)
    try:
        keyword_matches = _load_keyword_matches(database, topic)
        vector_count = database.execute("SELECT COUNT(*) FROM vectors").fetchone()[0]
        if not vector_count:
            raise RuntimeError(
                "The index contains no embeddings. Run `wikiwiki index` to build them."
            )
        ranked_chunks = _combine_matches(
            _load_semantic_matches(database, topic),
            keyword_matches,
        )
        return _book_results(ranked_chunks, limit, pages_per_book)
    finally:
        database.close()


__all__ = [
    "BookResult",
    "IndexedChunk",
    "PageMatch",
    "RankedChunk",
    "SCHEMA",
    "_book_results",
    "_combine_matches",
    "_snippet",
    "fingerprint",
    "rebuild",
    "search",
]
