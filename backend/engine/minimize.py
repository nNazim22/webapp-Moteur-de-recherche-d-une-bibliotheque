
from .dfa import DFA, DEAD


def minimize(dfa):
    n = len(dfa.states)
    symbols = list(dfa.delta[dfa.start].keys())      # meme alphabet pour tous les etats

    # --- 1. etats co-accessibles (qui peuvent atteindre un etat acceptant) ---x
    preds = [[] for _ in range(n)]
    for s in range(n):
        for t in dfa.delta[s].values():
            if t != DEAD:
                preds[t].append(s)
    alive = {s for s in range(n) if dfa.accepting[s]}
    stack = list(alive)
    while stack:
        s = stack.pop()
        for p in preds[s]:
            if p not in alive:
                alive.add(p)
                stack.append(p)

    def target(s, x):                                # successeur, DEAD si inutile
        t = dfa.delta[s][x]
        return t if t != DEAD and t in alive else DEAD

    if dfa.start not in alive:                       # langage vide (n'arrive pas avec nos regex)
        empty = DFA()
        empty.members = "DFA"
        empty.states = [frozenset({dfa.start})]
        empty.delta = [{x: DEAD for x in symbols}]
        empty.accepting = [False]
        return empty

    # --- 2./3. partition initiale puis raffinements successifs ---
    states = sorted(alive)
    cls = {s: int(dfa.accepting[s]) for s in states}
    cls[DEAD] = -1
    n_classes = len(set(cls[s] for s in states))
    while True:
        signature = {s: (cls[s],) + tuple(cls[target(s, x)] for x in symbols) for s in states}
        ids = {}
        new = {s: ids.setdefault(signature[s], len(ids)) for s in states}
        new[DEAD] = -1
        cls = new
        if len(ids) == n_classes:                    # plus aucune classe ne se scinde
            break
        n_classes = len(ids)

    # --- 4. construction du DFA minimal (numerotation par parcours depuis l'etat initial) ---
    members = {}                                     # classe -> etats d'origine
    for s in states:
        members.setdefault(cls[s], set()).add(s)

    order = {cls[dfa.start]: 0}                      # classe -> numero final
    queue = [dfa.start]
    rep = {cls[dfa.start]: dfa.start}                # un representant par classe
    while queue:
        s = queue.pop(0)
        for x in symbols:
            t = target(s, x)
            if t != DEAD and cls[t] not in order:
                order[cls[t]] = len(order)
                rep[cls[t]] = t
                queue.append(t)

    mini = DFA()
    mini.members = "DFA"                             # chaque etat = ensemble d'etats du DFA d'origine
    mini.start = 0
    ordered = sorted(order, key=order.get)
    for c in ordered:
        r = rep[c]
        mini.states.append(frozenset(members[c]))
        mini.accepting.append(dfa.accepting[r])
        mini.delta.append({x: (order[cls[target(r, x)]] if target(r, x) != DEAD else DEAD)
                           for x in symbols})
    return mini
