SPECIAL = set("|*+?.()\\")     

def is_simple_word(regex):
    return not any(c in SPECIAL for c in regex)


def carry_over(word):
    m = len(word)
    table = [0] * (m + 1)
    table[0] = -1
    cnd = 0                      
    pos = 1
    while pos < m:
        if word[pos] == word[cnd]:
            table[pos] = table[cnd]         
        else:
            table[pos] = cnd                 
            while cnd >= 0 and word[pos] != word[cnd]:
                cnd = table[cnd]             
        pos += 1
        cnd += 1
    table[m] = cnd
    return table


def kmp_find(word, text, table=None):
    
    m, n = len(word), len(text)
    if m == 0:
        return 0
    if table is None:
        table = carry_over(word)
    i = 0                         
    j = 0                         
    while i < n:
        if word[j] == text[i]:
            i += 1
            j += 1
            if j == m:
                return i - m      
        else:
            j = table[j]         
            if j < 0:             
                i += 1
                j = 0
    return -1


class KMPMatcher:

    def __init__(self, word):
        self.word = word
        self.table = carry_over(word)

    def search(self, text):
        return kmp_find(self.word, text, self.table) >= 0
