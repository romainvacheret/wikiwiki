from wikiwiki.pdf import UNKNOWN_CHAPTER, _chapter_for_page


def test_page_uses_most_recent_chapter_before_it():
    chapters = [(10, "First"), (30, "Second")]

    assert _chapter_for_page(9, chapters) == UNKNOWN_CHAPTER
    assert _chapter_for_page(20, chapters) == "First"
    assert _chapter_for_page(30, chapters) == "Second"

