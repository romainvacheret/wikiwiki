from wikiwiki.index import BookResult, PageMatch
from wikiwiki.selection import SelectionState


def make_results():
    return [
        BookResult(
            "Book A",
            "Author A",
            (
                PageMatch(1, "Chapter 1", "first", 1.0),
                PageMatch(2, "Chapter 1", "second", 0.9),
                PageMatch(3, "Chapter 2", "third", 0.8),
            ),
        )
    ]


def test_selection_state_supports_parent_and_child_toggles():
    state = SelectionState(make_results())
    chapter = state.pages_for_chapter(0, "Chapter 1")

    state.toggle(chapter)
    assert state.marker(chapter) == "☑"

    state.toggle({(0, 1)})
    assert state.marker(chapter) == "☐"
    assert len(state.selected_results()[0].pages) == 1


def test_selection_state_select_all_and_clear():
    state = SelectionState(make_results())

    state.select_all()
    assert len(state.selected_results()[0].pages) == 3

    state.clear()
    assert state.selected_results() == []
