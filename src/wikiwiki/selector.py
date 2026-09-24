from __future__ import annotations

from dataclasses import replace

from .index import BookResult, PageMatch


class SourceSelector:
    """Textual-backed hierarchical source selector."""

    def __init__(self, results: list[BookResult]):
        self.results = results

    def run(self) -> list[BookResult] | None:
        from textual.app import App, ComposeResult
        from textual.widgets import Footer, Header, Tree

        outer = self

        class SourceTree(Tree[str]):
            def on_key(self, event) -> None:
                if event.key == "space":
                    event.stop()
                    self.app.action_toggle()
                elif event.key == "enter":
                    event.stop()
                    self.app.action_confirm()

        class SelectorApp(App[list[BookResult] | None]):
            TITLE = "Select sources for the answer"
            BINDINGS = [
                ("space", "toggle", "Toggle"),
                ("a", "select_all", "All"),
                ("n", "select_none", "None"),
                ("enter", "confirm", "Confirm"),
                ("escape", "cancel", "Cancel"),
            ]

            def __init__(self):
                super().__init__()
                self.source_tree: SourceTree | None = None
                self.selected: set[tuple[int, int]] = set()
                self.leaf_nodes = []

            def compose(self) -> ComposeResult:
                yield Header()
                self.source_tree = SourceTree("Select sources for the answer", id="sources", data=("root",))
                self.source_tree.show_root = False
                yield self.source_tree
                yield Footer()

            def on_mount(self) -> None:
                assert self.source_tree is not None
                for result_index, result in enumerate(outer.results):
                    book = self.source_tree.root.add(
                        result.title,
                        data=("book", result_index),
                    )
                    chapters: dict[str, list[tuple[int, PageMatch]]] = {}
                    for page_index, match in enumerate(result.pages):
                        chapters.setdefault(match.chapter, []).append((page_index, match))
                    for chapter, matches in chapters.items():
                        chapter_node = book.add(chapter, data=("chapter", result_index, chapter))
                        for page_index, match in matches:
                            leaf = chapter_node.add(
                                f"page {match.page}: {match.snippet}",
                                data=("page", result_index, page_index),
                            )
                            self.leaf_nodes.append(leaf)
                    book.expand()
                    for child in book.children:
                        child.expand()
                self._refresh_labels()

            def _descendant_pages(self, node):
                if node.data and node.data[0] == "page":
                    return [(node.data[1], node.data[2])]
                pages = []
                for child in node.children:
                    if child.data and child.data[0] == "page":
                        pages.append((child.data[1], child.data[2]))
                    else:
                        pages.extend(self._descendant_pages(child))
                return pages

            def _state(self, node) -> str:
                pages = self._descendant_pages(node)
                selected = sum(page in self.selected for page in pages)
                if selected == 0:
                    return "☐"
                if selected == len(pages):
                    return "☑"
                return "☐"

            def _refresh_labels(self) -> None:
                assert self.source_tree is not None
                for book in self.source_tree.root.children:
                    book.label = f"{self._state(book)} {outer.results[book.data[1]].title}"
                    for chapter in book.children:
                        chapter.label = f"{self._state(chapter)} {chapter.data[2]}"
                        for page in chapter.children:
                            result_index, page_index = page.data[1:]
                            match = outer.results[result_index].pages[page_index]
                            marker = "☑" if (result_index, page_index) in self.selected else "☐"
                            page.label = f"{marker} page {match.page}: {match.snippet}"

            def action_toggle(self) -> None:
                node = self.source_tree.cursor_node if self.source_tree else None
                if node is None:
                    return
                pages = self._descendant_pages(node)
                if not pages:
                    return
                if all(page in self.selected for page in pages):
                    self.selected.difference_update(pages)
                else:
                    self.selected.update(pages)
                self._refresh_labels()

            def action_select_all(self) -> None:
                self.selected = {(r, p) for r, result in enumerate(outer.results) for p in range(len(result.pages))}
                self._refresh_labels()

            def action_select_none(self) -> None:
                self.selected.clear()
                self._refresh_labels()

            def action_confirm(self) -> None:
                selected = []
                for result_index, result in enumerate(outer.results):
                    pages = tuple(
                        match for page_index, match in enumerate(result.pages)
                        if (result_index, page_index) in self.selected
                    )
                    if pages:
                        selected.append(replace(result, pages=pages))
                self.exit(selected)

            def action_cancel(self) -> None:
                self.exit(None)

        return SelectorApp().run()


def select_sources(results: list[BookResult]) -> list[BookResult] | None:
    return SourceSelector(results).run()
