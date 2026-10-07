from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Tree

from .index import BookResult
from .selection import PageKey, SelectionState


class _SourceTree(Tree[str]):
    def on_key(self, event) -> None:
        if event.key == "space":
            event.stop()
            self.app.action_toggle()
        elif event.key == "enter":
            event.stop()
            self.app.action_confirm()


class _SelectorApp(App[list[BookResult] | None]):
    TITLE = "Select sources for the answer"
    BINDINGS = [
        ("space", "toggle", "Toggle"),
        ("a", "select_all", "All"),
        ("n", "select_none", "None"),
        ("enter", "confirm", "Confirm"),
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, results: list[BookResult]):
        super().__init__()
        self.results = results
        self.state = SelectionState(results)
        self.source_tree: _SourceTree | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        self.source_tree = _SourceTree(
            "Select sources for the answer",
            id="sources",
            data=("root",),
        )
        self.source_tree.show_root = False
        yield self.source_tree
        yield Footer()

    def on_mount(self) -> None:
        self._build_tree()
        self._refresh_labels()

    def _build_tree(self) -> None:
        assert self.source_tree is not None
        for result_index, result in enumerate(self.results):
            book = self.source_tree.root.add(
                result.title,
                data=("book", result_index),
                expand=True,
            )
            chapters = self._chapters_for(result_index)
            for chapter, page_indexes in chapters.items():
                chapter_node = book.add(
                    chapter,
                    data=("chapter", result_index, chapter),
                    expand=True,
                )
                for page_index in page_indexes:
                    page = result.pages[page_index]
                    chapter_node.add(
                        f"page {page.page}: {page.snippet}",
                        data=("page", result_index, page_index),
                    )

    def _chapters_for(self, result_index: int) -> dict[str, list[int]]:
        chapters: dict[str, list[int]] = {}
        for page_index, page in enumerate(self.results[result_index].pages):
            chapters.setdefault(page.chapter, []).append(page_index)
        return chapters

    def _page_keys(self, node) -> set[PageKey]:
        if node.data and node.data[0] == "page":
            return {(node.data[1], node.data[2])}
        if node.data and node.data[0] == "chapter":
            return self.state.pages_for_chapter(node.data[1], node.data[2])
        if node.data and node.data[0] == "book":
            return self.state.pages_for_book(node.data[1])

        pages = set()
        for child in node.children:
            pages.update(self._page_keys(child))
        return pages

    def _refresh_labels(self) -> None:
        assert self.source_tree is not None
        for book in self.source_tree.root.children:
            book_keys = self._page_keys(book)
            book.label = f"{self.state.marker(book_keys)} {self.results[book.data[1]].title}"
            for chapter in book.children:
                chapter_keys = self._page_keys(chapter)
                chapter.label = f"{self.state.marker(chapter_keys)} {chapter.data[2]}"
                for page in chapter.children:
                    result_index, page_index = page.data[1:]
                    match = self.results[result_index].pages[page_index]
                    marker = self.state.marker({(result_index, page_index)})
                    page.label = f"{marker} page {match.page}: {match.snippet}"

    def action_toggle(self) -> None:
        node = self.source_tree.cursor_node if self.source_tree else None
        if node is None:
            return
        self.state.toggle(self._page_keys(node))
        self._refresh_labels()

    def action_select_all(self) -> None:
        self.state.select_all()
        self._refresh_labels()

    def action_select_none(self) -> None:
        self.state.clear()
        self._refresh_labels()

    def action_confirm(self) -> None:
        self.exit(self.state.selected_results())

    def action_cancel(self) -> None:
        self.exit(None)


def select_sources(results: list[BookResult]) -> list[BookResult] | None:
    return _SelectorApp(results).run()
