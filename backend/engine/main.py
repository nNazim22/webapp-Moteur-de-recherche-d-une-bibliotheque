import sys
from regex_parser import parse, tree_lines
from nfa import build_nfa
from dfa import build_dfa
from minimize import minimize
from kmp import KMPMatcher, is_simple_word

FLAGS = ("--dfa", "--no-min", "--explain")

sys.setrecursionlimit(max(sys.getrecursionlimit(), 20000))


def compile_regex(regex, force_automaton=False, minimize_dfa=True):
    if is_simple_word(regex) and not force_automaton:
        return KMPMatcher(regex)
    dfa = build_dfa(build_nfa(parse(regex)), search=True)
    return minimize(dfa) if minimize_dfa else dfa


def explain(regex):
    tree = parse(regex)
    nfa = build_nfa(tree)
    dfa = build_dfa(nfa)
    mini = minimize(dfa)
    print(f"== etape 1 : arbre syntaxique de {regex!r}\n" + "\n".join(tree_lines(tree)))
    print(f"\n== etape 2 : NFA avec epsilon-transitions\n{nfa.dump()}")
    print(f"\n== etape 3 : DFA (methode des sous-ensembles)\n{dfa.dump()}")
    print(f"\n== etape 4 : DFA minimal\n{mini.dump()}")
    s_dfa = build_dfa(build_nfa(parse(regex)), search=True)
    print(f"\n== etape 5 : automate de recherche (facteur d'une ligne) : "
          f"{len(s_dfa.states)} etats, {len(minimize(s_dfa).states)} apres minimisation")


def main():
    flags = [a for a in sys.argv[1:] if a in FLAGS]
    args = [a for a in sys.argv[1:] if a not in FLAGS]
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   
    if "--explain" in flags:
        if len(args) != 1:
            sys.exit('usage: python src/main.py --explain "REGEX"')
        explain(args[0])
        return
    if len(args) != 2:
        sys.exit('usage: python src/main.py "REGEX" FICHIER [--dfa] [--no-min] | --explain "REGEX"')
    regex, path = args
    matcher = compile_regex(regex, force_automaton="--dfa" in flags, minimize_dfa="--no-min" not in flags)
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if matcher.search(line):
                print(line)


if __name__ == "__main__":
    main()
