"""Algorithme de Knuth-Morris-Pratt : recherche d'un mot dans un texte en O(n + m).

Variante « table optimisée » (Aho-Ullman / Wikipédia) : table[j] donne la position de
reprise dans le mot quand le caractère j ne correspond pas ; -1 signifie « on avance dans
le texte ». Le texte n'est jamais relu en arrière, donc chaque caractère est lu au plus
deux fois.
"""

SPECIAL = set("|*+?.()[]\\")   # métacaractères de notre syntaxe de regex


def is_simple_word(regex):
    """Vrai si la regex ne contient aucun métacaractère : un simple mot, traité par KMP."""
    return not any(c in SPECIAL for c in regex)


def carry_over(word):
    """Table de report (« carry-over ») du mot : prétraitement en O(m)."""
    m = len(word)
    table = [0] * (m + 1)
    table[0] = -1
    cnd = 0                      # indice, dans le mot, du prochain caractère du candidat courant
    pos = 1
    while pos < m:
        if word[pos] == word[cnd]:
            table[pos] = table[cnd]          # même caractère : on reprend aussi loin que lui
        else:
            table[pos] = cnd                 # on reprend après le plus long bord
            while cnd >= 0 and word[pos] != word[cnd]:
                cnd = table[cnd]             # on remonte la chaîne des bords
        pos += 1
        cnd += 1
    table[m] = cnd
    return table


def kmp_find(word, text, table=None):
    """Position de la première occurrence de `word` dans `text`, -1 s'il n'y en a pas."""
    m, n = len(word), len(text)
    if m == 0:
        return 0
    if table is None:
        table = carry_over(word)
    i = 0                         # position dans le texte
    j = 0                         # position dans le mot
    while i < n:
        if word[j] == text[i]:
            i += 1
            j += 1
            if j == m:
                return i - m      # occurrence trouvée
        else:
            j = table[j]          # décalage : on ne recule jamais dans le texte
            if j < 0:             # aucun bord : on passe au caractère suivant du texte
                i += 1
                j = 0
    return -1


class KMPMatcher:
    """Mot compilé (table calculée une fois) ; même interface que le DFA : .search(texte)."""

    def __init__(self, word):
        self.word = word
        self.table = carry_over(word)

    def search(self, text):
        return kmp_find(self.word, text, self.table) >= 0
