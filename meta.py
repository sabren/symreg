# metagrammar parser for python's Grammar file
import re
from collections import namedtuple as nt

# namedtuple types to model the grammar rules
Tok = nt('Tok', ['text'])         # special token (NAME,NUMBER,INDENT,etc)
Lit = nt('Lit', ['text'])         # string literal
Seq = nt('Seq', ['args'])         # sequence of patterns
Alt = nt('Alt', ['args'])         # set of alternative patterns
Rep = nt('Rep', ['args'])         # 1..n repetitions ('repeat')
Opt = nt('Opt', ['args'])         # 0..1 repetitions ('optional')
Orp = nt('Orp', ['args'])         # 0..n repetitions ('optional repeat')
Def = nt('Def', ['text','args'])  # rule definition
Ref = nt('Ref', ['text'])         # reference a known rule


class MetaScanner:

    lexer = re.compile(r"""
        (?P<SPACE>    \s+     )
      | (?P<NEWLINE>  $       )
      | (?P<COMMENT>  [#].*$  )
      | (?P<SPECIAL>  [A-Z]+  )  # special tokens (in upper case)
      | (?P<RULENAME> [a-z_]+ )
      | (?P<STRING>  '.*'     )  # luckily, none contain escapes or quotes
      | (?P<COLON>    :       )
      | (?P<LPAREN>   \(      )
      | (?P<RPAREN>   \)      )
      | (?P<LBRACK>   \[      )
      | (?P<RBRACK>   \]      )
      | (?P<PLUS>     \+      )
      | (?P<STAR>     \*      )
      | (?P<PIPE>     \|      )
    """, re.VERBOSE|re.MULTILINE)

    def __init__(self, text):
        self.text = text
        self.pos  = 0

    def tokens(self):
        """
        This yields a list of (token_type, matched_text) pairs.
        The token_type is one of the names defined above in the lexer regexp.
        """
        result = {}
        while self.pos < len(self.text):
            m = self.lexer.match(self.text, self.pos)
            if m: yield m.lastgroup, m.group(0)
            else: raise SyntaxError('bad token at postition %i' % self.pos)
            self.pos = m.end()


if __name__=="__main__":
    s = MetaScanner(open('Grammar').read())
    for token in s.tokens():
        print(token)
