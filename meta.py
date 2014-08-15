# metagrammar parser for python's Grammar file
import re
from collections import namedtuple as nt
from contextlib import contextmanager
from itertools import chain

# namedtuple types to model the grammar rules
Tok = nt('Tok', ['text'])         # special token (NAME,NUMBER,INDENT,etc)
Lit = nt('Lit', ['text'])         # string literal
Seq = nt('Seq', ['args'])         # sequence of patterns
Alt = nt('Alt', ['args'])         # set of alternative patterns
Rep = nt('Rep', ['args'])         # 1..n repetitions ('repeat')
Opt = nt('Opt', ['args'])         # 0..1 repetitions ('optional')
Orp = nt('Orp', ['args'])         # 0..n repetitions ('optional repeat')
Def = nt('Def', ['name','rule'])  # rule definition
Ref = nt('Ref', ['text'])         # reference a known rule

Grammar = nt('Grammar', ['rules'])
Token = nt('Token', ['kind', 'text'])

class MetaScanner:

    lexer = re.compile(r"""
        (?P<NEWLINE>  \n      )  # this comes first so SPACE doesn't match it.
      | (?P<SPACE>    \s+     )
      | (?P<COMMENT>  [#].*$  )
      | (?P<SPECIAL>  [A-Z]+  )  # special tokens (in upper case)
      | (?P<RULENAME> [a-z_]+ )
      | (?P<STRING>  '[^']*'     )  # luckily, none contain escapes or quotes
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
        while self.pos < len(self.text):
            m = self.lexer.match(self.text, self.pos)
            self.pos = m.end()
            if m: yield Token(kind=m.lastgroup, text=m.group(0))
            else: raise SyntaxError('bad token at postition %i' % self.pos)


class MetaParser:
    """
    Builds a dictionary mapping rule names to grammar rules,
    each of which is represented as a tree of tuples.
    """

    def __init__(self, scanner:MetaScanner):
        self.here = []         # tracks the list where we will insert nodes
        self.stack = []        # stores current context (composed of such lists)
        self.token = Token("START",'')  # tracks the current token
        self.tokens = chain((tok for tok in scanner.tokens()
                            if tok.kind not in {"SPACE","COMMENT"}),
                            [Token("EOF",'')])

    def advance(self):
        self.token = next(self.tokens)
        print(self.token)
        return self.token

    def expect(self, token_kind):
        if self.token.kind == token_kind:
            result = self.token
            self.advance()
        else:
            raise SyntaxError('expected %s but found %s'
                              % (token_kind, self.token.kind))
        return result

    def skip_any(self, token_kind):
        while self.token.kind == token_kind:
            self.advance()

    def descend(self, new_context):
        self.stack.append(self.here)
        self.here = new_context

    def ascend(self):
        self.here = self.stack.pop()

    @contextmanager
    def context(self):
        ctx = []
        self.descend(ctx)
        yield ctx
        self.ascend()

    def emit(self, node):
        self.here.append(node)

    def wrap_last_as(self, wrapper):
        assert len(self.here), "tried to wrap as %r but nothing to wrap!" % wrapper
        last = self.here.pop()
        self.here.append(wrapper(last))


    # --- recursive descent parser starts here ---

    def parse(self):
        self.expect('START')
        with self.context() as defs:
            while self.token.kind != 'EOF':
                self.skip_any('NEWLINE')
                if self.token.kind == 'EOF': pass
                else: defs.append(self.read_def())
        return Grammar(defs)

    def read_def(self):
        name = self.expect('RULENAME').text
        self.expect('COLON')
        with self.context() as rule:
            rule.append(self.read_pattern('NEWLINE'))
        return Def(name, rule)

    def read_pattern(self, end_kind):
        alts = []
        with self.context() as alt:
            while self.token.kind != end_kind:
                k,text = self.token # kind and text
                if k == end_kind: pass # we're done.
                elif k=='NEWLINE': pass # newlines ok when end_kind != NEWLINE
                elif k=='PIPE': # start a new alternative
                    alts.append(alt)
                    self.ascend()
                    alt = []
                    self.descend(alt)
                elif k=='SPECIAL':
                    self.emit(Tok(text))
                elif k=='RULENAME':
                    self.emit(Ref(text))
                elif k=='LPAREN':
                    self.advance()
                    self.emit(self.read_pattern('RPAREN'))
                elif k=='LBRACK':
                    self.advance()
                    self.emit(Opt(self.read_pattern('RBRACK')))
                elif k=='STAR':
                    self.wrap_last_as(Orp)
                elif k=='PLUS':
                    self.wrap_last_as(Rep)
                elif k=='STRING':
                    self.emit(Lit(text[1:-1]))
                else: raise SyntaxError('ERROR unrecognized token.', self.token)
                k = self.advance()
            # end of loop:
            alts.append(alt)
            if len(alts) == 1:
                return Seq(alts[0])
            else: return Alt(alts)




if __name__=="__main__":
    scanner = MetaScanner(open('Grammar').read())
    parser = MetaParser(scanner)
    print(parser.parse())
