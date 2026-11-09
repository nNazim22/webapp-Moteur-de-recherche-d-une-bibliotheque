
from regex_parser import CHAR, DOT, EPS, CONCAT, UNION, STAR

EPSILON = None   
ANY = "ANY"      

class NFA:
    def __init__(self):
        self.n = 0                 
        self.trans = []            
        self.start = None
        self.accept = None

    def new_state(self):
        self.trans.append([])
        self.n += 1
        return self.n - 1

    def add(self, src, label, dst):
        self.trans[src].append((label, dst))

    def dump(self):
        lines = [f"etats={self.n} initial={self.start} final={self.accept}"]
        for s in range(self.n):
            for lab, t in self.trans[s]:
                lines.append(f"  {s} --{'ε' if lab is EPSILON else lab}--> {t}")
        return "\n".join(lines)

    def eps_closure(self, states):
        stack, seen = list(states), set(states)
        while stack:
            s = stack.pop()
            for lab, t in self.trans[s]:
                if lab is EPSILON and t not in seen:
                    seen.add(t)
                    stack.append(t)
        return seen

    def accepts(self, word):
    
        cur = self.eps_closure({self.start})
        for ch in word:
            nxt = set()
            for s in cur:
                for lab, t in self.trans[s]:
                    if lab == ch or lab == ANY:
                        nxt.add(t)
            cur = self.eps_closure(nxt)
            if not cur:
                return False
        return self.accept in cur


def build_nfa(tree):
    nfa = NFA()

    def build(node):
        if node.kind in (CHAR, DOT, EPS):                
            s, f = nfa.new_state(), nfa.new_state()
            label = {CHAR: node.char, DOT: ANY, EPS: EPSILON}[node.kind]
            nfa.add(s, label, f)
            return s, f
        if node.kind == UNION:                           
            a_s, a_f = build(node.left)
            b_s, b_f = build(node.right)
            s, f = nfa.new_state(), nfa.new_state()
            nfa.add(s, EPSILON, a_s); nfa.add(s, EPSILON, b_s)
            nfa.add(a_f, EPSILON, f); nfa.add(b_f, EPSILON, f)
            return s, f
        if node.kind == CONCAT:                          
            a_s, a_f = build(node.left)
            b_s, b_f = build(node.right)
            nfa.add(a_f, EPSILON, b_s)
            return a_s, b_f
        if node.kind == STAR:                            
            a_s, a_f = build(node.left)
            s, f = nfa.new_state(), nfa.new_state()
            nfa.add(s, EPSILON, a_s); nfa.add(s, EPSILON, f)
            nfa.add(a_f, EPSILON, a_s); nfa.add(a_f, EPSILON, f)
            return s, f
        raise ValueError(node.kind)

    nfa.start, nfa.accept = build(tree)
    return nfa
