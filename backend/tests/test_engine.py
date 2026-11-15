"""Tests du moteur du projet 1 : KMP, parseur, NFA, DFA, minimisation.

Le test central compare notre moteur à `re.search` de Python sur des centaines de
regex tirées au hasard : c'est la preuve de correction citée dans le rapport.
"""
import random
import re

import pytest

from engine import KMPMatcher, build_dfa, build_nfa, compile_regex, minimize, parse
from engine.kmp import carry_over, is_simple_word, kmp_find
from engine.regex_parser import RegexSyntaxError

# ---------------------------------------------------------------- KMP


@pytest.mark.parametrize("word,text,expected", [
    ("whale", "the white whale", 10),
    ("aab", "aaaab", 2),                 # chevauchement : cas qui piège les implémentations naïves
    ("abab", "abaabab", 3),
    ("x", "abc", -1),
    ("abc", "ab", -1),                   # mot plus long que le texte
    ("", "abc", 0),
])
def test_kmp_find(word, text, expected):
    assert kmp_find(word, text) == expected == (text.find(word))


def test_kmp_agrees_with_str_find_on_random_texts():
    rnd = random.Random(1)
    for _ in range(500):
        word = "".join(rnd.choice("ab") for _ in range(rnd.randint(1, 6)))
        text = "".join(rnd.choice("ab") for _ in range(rnd.randint(0, 30)))
        assert kmp_find(word, text) == text.find(word)


def test_kmp_table_is_linear_and_reusable():
    assert carry_over("abab") == [-1, 0, -1, 0, 2]
    matcher = KMPMatcher("ana")
    assert matcher.search("banana") and not matcher.search("bonbon")


def test_is_simple_word():
    assert is_simple_word("whale") and not is_simple_word("wh.le") and not is_simple_word("[ab]")

# ---------------------------------------------------------------- parseur


def test_parse_priorities():
    assert repr(parse("ab|c*")) == "((a·b)|(c)*)"          # * > concaténation > |
    assert repr(parse("a+")) == "(a·(a)*)"
    assert repr(parse("a?")) == "(a|ε)"


@pytest.mark.parametrize("bad", ["a(b", "a)", "*a", "a|*", "[abc", "[]", "[z-a]", "\\"])
def test_parse_errors(bad):
    with pytest.raises(RegexSyntaxError):
        parse(bad)


def test_character_class():
    dfa = build_dfa(build_nfa(parse("[a-c]x")))
    assert dfa.accepts("bx") and not dfa.accepts("dx")
    assert compile_regex("gr[ae]y").search("a grey cat") and compile_regex("gr[ae]y").search("gray")
    assert not compile_regex("gr[ae]y").search("griy")


def test_huge_range_is_refused():
    with pytest.raises(RegexSyntaxError):
        parse("[a-\U0010ffff]")

# ---------------------------------------------------------------- automates


def test_nfa_dfa_minimal_dfa_accept_the_same_words():
    regex = "(a|b)*abb"
    nfa = build_nfa(parse(regex))
    dfa = build_dfa(nfa)
    mini = minimize(dfa)
    for w in ["abb", "aabb", "babb", "ab", "abba", "", "bbabb"]:
        expected = re.fullmatch(regex, w) is not None
        assert nfa.accepts(w) == dfa.accepts(w) == mini.accepts(w) == expected


def test_minimization_shrinks_the_classical_example():
    dfa = build_dfa(build_nfa(parse("(a|b)*abb")))
    mini = minimize(dfa)
    assert len(mini.states) == 4 <= len(dfa.states)      # exemple du cours : 4 états


def test_search_automaton_finds_factors():
    m = compile_regex("a.c|xy+")
    assert m.search("zzabczz") and m.search("..xyyy") and not m.search("ab xz")


def test_dot_matches_any_unicode_character():
    assert compile_regex("caf.").search("café")


def test_force_automaton_for_simple_word():
    assert compile_regex("whale", force_automaton=True).search("a whale") is True

# ---------------------------------------------------------------- équivalence avec re


def random_regex(rnd, depth=0):
    """Regex aléatoire dans la syntaxe gérée par le moteur."""
    r = rnd.random()
    if depth > 3 or r < 0.30:
        return rnd.choice(["a", "b", "c", ".", "[ab]", "[a-c]"])
    if r < 0.50:
        return random_regex(rnd, depth + 1) + random_regex(rnd, depth + 1)
    if r < 0.65:
        return "(" + random_regex(rnd, depth + 1) + "|" + random_regex(rnd, depth + 1) + ")"
    atom = "(" + random_regex(rnd, depth + 1) + ")"
    return atom + rnd.choice(["*", "+", "?"])


def test_engine_agrees_with_python_re_on_random_regexes():
    rnd = random.Random(2024)
    words = ["".join(rnd.choice("abcd") for _ in range(rnd.randint(0, 9))) for _ in range(60)]
    for _ in range(300):
        regex = random_regex(rnd)
        matcher = compile_regex(regex, force_automaton=True)
        for w in words:
            assert matcher.search(w) == (re.search(regex, w) is not None), (regex, w)


def test_minimal_dfa_never_larger_than_dfa():
    rnd = random.Random(7)
    for _ in range(100):
        regex = random_regex(rnd)
        dfa = build_dfa(build_nfa(parse(regex)), search=True)
        assert len(minimize(dfa).states) <= len(dfa.states)
