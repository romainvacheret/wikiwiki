from __future__ import annotations

from dataclasses import dataclass

import pymupdf


@dataclass(frozen=True)
class ExtractedPage:
    number: int
    chapter: str
    text: str


UNKNOWN_CHAPTER = "Unknown chapter"


def _chapters(document) -> list[tuple[int, str]]:
    return [
        (entry[2], entry[1])
        for entry in document.get_toc(simple=True)
        if len(entry) >= 3 and entry[0] <= 2 and entry[2] > 0
    ]


def _chapter_for_page(page_number: int, chapters: list[tuple[int, str]]) -> str:
    chapter = UNKNOWN_CHAPTER
    for chapter_page, title in chapters:
        if chapter_page > page_number:
            break
        chapter = title
    return chapter


def extract_pages(path) -> list[ExtractedPage]:
    document = pymupdf.open(path)
    try:
        chapters = _chapters(document)
        return [
            ExtractedPage(
                number=page_number,
                chapter=_chapter_for_page(page_number, chapters),
                text=text,
            )
            for page_number, page in enumerate(document, start=1)
            if (text := page.get_text("text").strip())
        ]
    finally:
        document.close()
