from .nfa import EPSILON, ANY

OTHER = "OTHER"
DEAD = -1          #


class DFA:
    def __init__(self):
        self.states = []      
        self.delta = []        
        self.accepting = []    
        self.start = 0
        self.members = "NFA"   

    def step(self, s, ch):
        d = self.delta[s]
        return d[ch] if ch in d else d[OTHER]

    def accepts(self, word):
        s = self.start
        for ch in word:
            s = self.step(s, ch)
            if s == DEAD:
                return False
        return self.accepting[s]

    def search(self, text):
        
        s = self.start
        if self.accepting[s]:
            return True
        for ch in text:
            s = self.step(s, ch)
            if self.accepting[s]:      
                return True
        return False

    def dump(self):
        lines = [f"{len(self.states)} etats, initial={self.start}"]
        for i, S in enumerate(self.states):
            mark = " (acceptant)" if self.accepting[i] else ""
            lines.append(f"  etat {i} = {self.members}{sorted(S)}{mark}")
            for ch, t in self.delta[i].items():
                if t != DEAD:
                    lines.append(f"      --{ch}--> {t}")
        return "\n".join(lines)


def build_dfa(nfa, search=False):
    alphabet = {lab for trans in nfa.trans for lab, _ in trans if lab is not EPSILON and lab != ANY}
    symbols = sorted(alphabet) + [OTHER]

    start_closure = frozenset(nfa.eps_closure({nfa.start}))

    dfa = DFA()
    index = {}                         

    def add_state(S):
        index[S] = len(dfa.states)
        dfa.states.append(S)
        dfa.delta.append({})
        dfa.accepting.append(nfa.accept in S)
        return index[S]

    dfa.start = add_state(start_closure)
    todo = [start_closure]
    while todo:
        S = todo.pop()
        i = index[S]
        for x in symbols:
           
            moved = {t for s in S for lab, t in nfa.trans[s]
                     if lab == ANY or (x != OTHER and lab == x)}
            T = nfa.eps_closure(moved) if moved else set()
            if search:
                T = T | start_closure   
            if not T:
                dfa.delta[i][x] = DEAD
                continue
            T = frozenset(T)
            if T not in index:
                add_state(T)
                todo.append(T)
            dfa.delta[i][x] = index[T]
    return dfa
