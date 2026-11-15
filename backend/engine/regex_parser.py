"""Analyse syntaxique d'une expression régulière -> arbre syntaxique.

Grammaire gérée (priorités croissantes : | puis concaténation puis * + ? puis atome) :
    regex   ::= concat ( '|' concat )*
    concat  ::= facteur*                      (vide = epsilon)
    facteur ::= atome ( '*' | '+' | '?' )*
    atome   ::= '(' regex ')' | '.' | '[' classe ']' | '\\' c | c
    classe  ::= ( c | c '-' c )+              (ex. [abc], [a-z0-9], [éè])

Un atome « classe » est ramené à une union de caractères, donc le reste de la chaîne
(NFA de Thompson, déterminisation, minimisation) n'a pas à le connaître.
Non gérés : ancres ^ $, classes négatives [^...], répétitions {n,m}, groupes nommés.
"""

# Types de noeuds
CHAR, DOT, EPS, CONCAT, UNION, STAR = "CHAR", "DOT", "EPS", "CONCAT", "UNION", "STAR"
MAX_RANGE = 512          # taille maximale d'un intervalle [a-z] (évite [\x00-\U0010ffff])


class Node:
    def __init__(self, kind, char=None, left=None, right=None):
        self.kind = kind      # l'un des types ci-dessus
        self.char = char      # pour CHAR : le caractère
        self.left = left      # fils gauche (ou unique fils pour STAR)
        self.right = right    # fils droit

    def __repr__(self):
        if self.kind == CHAR:
            return self.char
        if self.kind == DOT:
            return "."
        if self.kind == EPS:
            return "ε"
        if self.kind == STAR:
            return f"({self.left})*"
        if self.kind == CONCAT:
            return f"({self.left}·{self.right})"
        return f"({self.left}|{self.right})"


class RegexSyntaxError(Exception):
    """Expression régulière mal formée (message en français, affiché à l'utilisateur)."""


class Parser:
    def __init__(self, text):
        self.s = text
        self.i = 0

    def peek(self):
        return self.s[self.i] if self.i < len(self.s) else None

    def eat(self, c=None):
        ch = self.peek()
        if ch is None or (c is not None and ch != c):
            raise RegexSyntaxError(f"attendu {c!r} a la position {self.i} dans {self.s!r}")
        self.i += 1
        return ch

    def parse(self):
        node = self.regex()
        if self.peek() is not None:
            raise RegexSyntaxError(f"caractere inattendu {self.peek()!r} a la position {self.i}")
        return node

    def regex(self):
        left = self.concat()
        while self.peek() == "|":
            self.eat("|")
            right = self.concat()
            left = Node(UNION, left=left, right=right)
        return left

    def concat(self):
        if self.peek() in (None, "|", ")"):
            return Node(EPS)
        left = self.facteur()
        while self.peek() not in (None, "|", ")"):
            right = self.facteur()
            left = Node(CONCAT, left=left, right=right)
        return left

    def facteur(self):
        node = self.atome()
        while self.peek() in ("*", "+", "?"):
            op = self.eat()
            if op == "*":
                node = Node(STAR, left=node)
            elif op == "+":
                node = Node(CONCAT, left=node, right=Node(STAR, left=clone(node)))
            else:
                node = Node(UNION, left=node, right=Node(EPS))
        return node

    def classe(self):
        """Lit le contenu d'une classe après '[' (jusqu'à ']') et renvoie l'union de ses caractères."""
        chars = []
        while self.peek() not in (None, "]"):
            c = self.eat()
            if c == "\\":
                c = self.eat()
            if self.peek() == "-" and self.i + 1 < len(self.s) and self.s[self.i + 1] != "]":
                self.eat("-")
                hi = self.eat()
                if hi == "\\":
                    hi = self.eat()
                if ord(hi) < ord(c):
                    raise RegexSyntaxError(f"intervalle invalide {c}-{hi} dans {self.s!r}")
                if ord(hi) - ord(c) >= MAX_RANGE:
                    raise RegexSyntaxError(f"intervalle trop grand {c}-{hi} (max {MAX_RANGE} caractères)")
                chars.extend(chr(o) for o in range(ord(c), ord(hi) + 1))
            else:
                chars.append(c)
        self.eat("]")
        if not chars:
            raise RegexSyntaxError(f"classe vide dans {self.s!r}")
        node = None
        for c in dict.fromkeys(chars):                  # sans doublon, ordre conservé
            leaf = Node(CHAR, char=c)
            node = leaf if node is None else Node(UNION, left=node, right=leaf)
        return node

    def atome(self):
        ch = self.peek()
        if ch == "[":
            self.eat("[")
            return self.classe()
        if ch == "(":
            self.eat("(")
            node = self.regex()
            self.eat(")")
            return node
        if ch == ".":
            self.eat()
            return Node(DOT)
        if ch == "\\":
            self.eat()
            return Node(CHAR, char=self.eat())
        if ch in ("*", "+", "?", ")", "|", None):
            raise RegexSyntaxError(f"atome attendu a la position {self.i} dans {self.s!r}")
        return Node(CHAR, char=self.eat())    # caractère ordinaire (']' isolé inclus)


def clone(n):
    if n is None:
        return None
    return Node(n.kind, n.char, clone(n.left), clone(n.right))


def parse(text):
    return Parser(text).parse()


def tree_lines(node, prefix="", is_root=True, is_last=True):
    label = {CHAR: node.char, DOT: ".", EPS: "ε", CONCAT: "·", UNION: "|", STAR: "*"}[node.kind]
    if is_root:
        lines, child_prefix = [label], ""
    else:
        lines = [prefix + ("└── " if is_last else "├── ") + label]
        child_prefix = prefix + ("    " if is_last else "│   ")
    kids = [k for k in (node.left, node.right) if k is not None]
    for idx, k in enumerate(kids):
        lines += tree_lines(k, child_prefix, False, idx == len(kids) - 1)
    return lines


if __name__ == "__main__":
    import sys
    regex = sys.argv[1] if len(sys.argv) > 1 else "a|bc*"
    tree = parse(regex)
    print(regex, "->", tree)
    print("\n".join(tree_lines(tree)))
