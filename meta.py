# metagrammar parser for python's Grammar file
import re, sys
from collections import namedtuple as nt
from contextlib import contextmanager
from itertools import chain
from warnings import warn

# namedtuple types to model the grammar rules
Tok = nt('Tok', ['text'])         # special token (NAME,NUMBER,INDENT,etc)
Lit = nt('Lit', ['text'])         # string literal
Seq = nt('Seq', ['args'])         # sequence of patterns
Alt = nt('Alt', ['args'])         # set of alternative patterns
Rep = nt('Rep', ['args'])         # 1..n repetitions ('repeat')
Opt = nt('Opt', ['args'])         # 0..1 repetitions ('optional')
Orp = nt('Orp', ['args'])         # 0..n repetitions ('optional repeat')
Def = nt('Def', ['name','args'])  # rule definition. works like named Seq
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

    def tokens(self, text):
        """
        This yields a list of (token_type, matched_text) pairs.
        The token_type is one of the names defined above in the lexer regexp.
        """
        pos = 0
        while pos < len(text):
            m = self.lexer.match(text, pos)
            pos = m.end()
            if m: yield Token(kind=m.lastgroup, text=m.group(0))
            else: raise SyntaxError('bad token at postition %i' % pos)


class MetaParser:
    """
    Builds a dictionary mapping rule names to grammar rules,
    each of which is represented as a tree of tuples.
    """

    def __init__(self, scanner:MetaScanner):
        self.here = []         # tracks the list where we will insert nodes
        self.stack = []        # stores current context (composed of such lists)
        self.scanner = scanner
        self.set_text('')

    def set_text(self, text):
        self.token = Token("START",'')  # tracks the current token
        self.tokens = chain((tok for tok in self.scanner.tokens(text)
                            if tok.kind not in {"SPACE","COMMENT"}),
                            [Token("EOF",'')])

    def advance(self):
        self.token = next(self.tokens)
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

    def parse(self, text):
        self.set_text(text)
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
            return Seq(alts[0]) if len(alts) == 1 else Alt(alts)


class GrammarWalker:

    def __init__(self, visitor:object):
        self.visitor = visitor

    def method(self, prefix:str, node:nt):
        kind = type(node).__name__
        return getattr(self.visitor, prefix+kind, None)

    def dispatch(self, prefix:str, node:nt):
        meth = self.method(prefix, node)
        if meth: return meth(node)
        else: return None

    def children(self, node:nt):
        kind = type(node)
        if   kind is Def: result = [node.rule]
        elif kind is Grammar: result = node.rules
        elif kind in [Seq,Alt,Rep,Opt,Orp]:
            result = [node.args] # wrap as list just to simplify.
        elif kind in [Tok,Lit,Ref]: result = [] # no children
        elif kind is list: result = node
        else:
            print('\n\nERROR ON:', node, '\n\n')
            raise Exception('unknown node kind: ' + kind.__name__)
            result = []
        assert type(result) is list, \
            'malformed result: %r for node: %r' % (result, node)
        return result

    def walk(self, node:nt):
        """
        By default, provides sax-style walking. The visitor should have
        methods like `enterTok(x:Tok)`, `leaveTok(x:Tok)`, `enterLit(x:Lit)` etc..

        Alternatively, if you provide a method like `walkDef(walk, x:Def)`.
        Then there will be no automatic recursive descent and you can provide
        your own tree-walking logic. The 'walk' param will be this method.

        These two approaches are mutually exclusive. The 'walk' version takes
        precedence. All of the methods are optional.
        """
        custom = self.method('walk', node)
        if custom: custom(self.walk, node)
        else:
            self.dispatch('enter', node)
            for child in self.children(node):
                self.walk(child)
            self.dispatch('leave', node)

def parse(text):
    scanner = MetaScanner()
    parser = MetaParser(scanner)
    return parser.parse(text)

_pygrammar = None
def python_grammar():
    global _pygrammar
    if not _pygrammar: _pygrammar = parse(open('Grammar').read())
    return _pygrammar


def hacky_rules():
    """
    this is a quick and dirty method to read one rule at a time.
    so i can test the real parser.
    """
    name = chunk = None
    rule_start = re.compile('^[a-z_]+:')
    for line in open('Grammar'):
        if line.startswith("#") or line.strip() == "": pass
        elif rule_start.match(line):
            if chunk: yield (name, ''.join(chunk))
            name = line.split(':')[0]
            chunk = [line]
        else: chunk.append(line)
    yield (name, ''.join(chunk))


def walk_python(visitor:object):
    """
    walk the python metagrammar
    """
    GrammarWalker(visitor).walk(python_grammar())


# these two can be passed as literals to Emitter.emit()
class INDENT:pass
class DEDENT:pass

class Emitter:
    def __init__(self, emitFn=sys.stdout.write):
        self.emitFn = emitFn
        self.level = 0
        self.indent_str = '    '

    def emit(self, s:str):
        if s == '\n': self.newline()
        elif s is INDENT:
            self.indent(); self.newline()
        elif s is DEDENT:
            self.dedent(); self.newline()
        else: self.emitFn(s)

    def indent(self):
        self.level += 1

    def dedent(self):
        self.level -= 1
        assert self.level >= 0, 'cannot dedent any further!'

    def newline(self):
        self.emitFn('\n' + self.indent_str * self.level)

    def indentation(self):
        return self.indent_str * self.level

    def between(self, walk, nodes, sep):
        """sort of like sep.join(nodes) but imperative"""
        if nodes:
            walk(nodes[0])
            for node in nodes[1:]:
                self.emit(sep)
                walk(node)

    def emitAll(self, *strings):
        for s in strings: self.emit(s)


class EBNFEmitter(Emitter):
    """
    This emits the grammar back in the EBNF-style syntax
    that python's metagrammar uses, so we can test it.
    """

    def enterTok(self, node:Tok):
        self.emit(node.text)

    def enterLit(self, node:Lit):
        self.emitAll("'", node.text, "'")

    def enterRef(self, node:Ref):
        self.emit(node.text)

    def walkDef(self, walk, node:Def):
        self.emitAll(node.name, ': ')
        walk(node.args)
        self.emit('\n')

    def walkSeq(self, walk, node:Seq):
        self.between(walk, node.args, ' ')

    def walklist(self, walk, node:list):
        # lists in the AST can be treated just like sequences
        self.between(walk, node, ' ')

    def walkAlt(self, walk, node:Seq):
        self.emit('(')
        self.between(walk, node.args, ' | ')
        self.emit(')')

    def walkOpt(self, walk, node:Opt):
        self.emit('[')
        walk(node.args)
        self.emit(']')

    def walkOrp(self, walk, node:Opt):
        self.emit('(')
        walk(node.args)
        self.emit(')*')


emit = lambda node: GrammarWalker(EBNFEmitter()).walk(node)
if __name__=="__main__":
    #walk_python(EBNFEmitter())
    #rule = python_grammar().rules[0]
    for rule_name, rule_txt in hacky_rules():
        #if rule_name not in ['arglist']: continue
        print('----')
        print()
        print(rule_txt.strip())  # show the original text
        rule = parse(rule_txt)
        #print(rule)      # shows the nested AST
        emit(rule)       # shows the re-generated text
        print()
