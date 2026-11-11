"""Moteur du projet 1 : KMP et regex -> NFA -> DFA.

Usage depuis le reste du projet :
    from engine import compile_regex
    matcher = compile_regex("a(b|c)*d")
    matcher.search("xxabcbd")   # True si le texte contient une chaîne vérifiant la regex
"""
from .kmp import KMPMatcher, is_simple_word
from .regex_parser import parse
from .nfa import build_nfa
from .dfa import build_dfa
from .minimize import minimize


def compile_regex(regex, force_automaton=False, minimize_dfa=True):
    """Renvoie un objet avec une méthode .search(texte).

    Mot simple (lettres seulement) -> KMP ; sinon -> DFA de recherche minimisé.
    """
    if is_simple_word(regex) and not force_automaton:
        return KMPMatcher(regex)
    dfa = build_dfa(build_nfa(parse(regex)), search=True)
    return minimize(dfa) if minimize_dfa else dfa