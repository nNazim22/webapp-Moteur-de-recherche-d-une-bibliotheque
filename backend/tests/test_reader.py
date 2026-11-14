"""Tests du découpage en pages et de la recherche des pages contenant des mots."""
from app.reader import find_hit_pages, format_paragraph, split_pages

PROSE = ("It was the best of times, it was the worst of times, it was the age of\n"
         "wisdom, it was the age of foolishness, it was the epoch of belief, it was\n"
         "the epoch of incredulity.")
VERSE = "Roses are red,\nViolets are blue,\nSugar is sweet."


def test_prose_is_reflowed_into_one_line():
    out = format_paragraph(PROSE)
    assert "\n" not in out and out.startswith("It was the best of times")


def test_verse_keeps_its_line_breaks():
    assert format_paragraph(VERSE) == VERSE


def test_empty_paragraph():
    assert format_paragraph("  \n \n") == ""


def test_split_pages_groups_paragraphs():
    text = "\n\n".join(f"Paragraph number {i} " + "word " * 20 for i in range(10))
    pages = split_pages(text, page_chars=300)
    assert len(pages) > 1
    assert sum(len(p) for p in pages) == 10                   # aucun paragraphe perdu
    assert all(isinstance(par, str) for p in pages for par in p)


def test_split_pages_handles_windows_line_endings():
    pages = split_pages("First paragraph.\r\n\r\nSecond paragraph.\r\n", page_chars=10)
    assert [list(p) for p in pages] == [["First paragraph."], ["Second paragraph."]]


def test_split_pages_empty_text():
    assert split_pages("") == ()


PAGES = (("The whale swims.",), ("A wheel and a whale.",), ("Nothing here, only wheat.", "Whaler ships."))


def test_hits_whole_word():
    assert find_hit_pages(PAGES, ["whale"]) == [1, 2]          # pas « whaler »


def test_hits_substring():
    assert find_hit_pages(PAGES, ["whale"], whole=False) == [1, 2, 3]


def test_hits_multiple_terms_and_case():
    assert find_hit_pages(PAGES, ["WHEEL", "wheat"]) == [2, 3]


def test_hits_no_terms():
    assert find_hit_pages(PAGES, []) == []


def test_hits_apostrophe_splits_words_like_the_index():
    assert find_hit_pages((("Don't go.",),), ["don"]) == [1]