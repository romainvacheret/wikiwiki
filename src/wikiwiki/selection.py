from __future__ import annotations

from dataclasses import replace

from .index import BookResult


PageKey = tuple[int, int]


class SelectionState:
    def __init__(self, results: list[BookResult]):
        self.results = results
        self.selected: set[PageKey] = set()

    def pages_for_book(self, result_index: int) -> set[PageKey]:
        return {
            (result_index, page_index)
            for page_index in range(len(self.results[result_index].pages))
        }

    def pages_for_chapter(self, result_index: int, chapter: str) -> set[PageKey]:
        return {
            (result_index, page_index)
            for page_index, page in enumerate(self.results[result_index].pages)
            if page.chapter == chapter
        }

    def toggle(self, pages: set[PageKey]) -> None:
        if pages and pages <= self.selected:
            self.selected.difference_update(pages)
        else:
            self.selected.update(pages)

    def select_all(self) -> None:
        self.selected = {
            (result_index, page_index)
            for result_index, result in enumerate(self.results)
            for page_index in range(len(result.pages))
        }

    def clear(self) -> None:
        self.selected.clear()

    def marker(self, pages: set[PageKey]) -> str:
        if pages and pages <= self.selected:
            return "☑"
        return "☐"

    def is_selected(self, page: PageKey) -> bool:
        return page in self.selected

    def selected_results(self) -> list[BookResult]:
        selected_results = []
        for result_index, result in enumerate(self.results):
            pages = tuple(
                page
                for page_index, page in enumerate(result.pages)
                if (result_index, page_index) in self.selected
            )
            if pages:
                selected_results.append(replace(result, pages=pages))
        return selected_results

