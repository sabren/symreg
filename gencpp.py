import sys, io
import meta
from meta import Tok, Lit, Ref, Def, Seq, Alt, Opt, Orp, Rep, Seq
from meta import INDENT, DEDENT


class CPPEmitter(meta.Emitter):
    """
    This emits a C++ program based on the python grammar.
    The program, when run, generates a random python program.
    """
    def walkDef(self, walk, node:Def):
        self.emitAll('void ', node.name, '() {', INDENT)
        walk(node.args)
        self.emitAll(DEDENT, '}', '\n')

    def cout(self, *args):
        self.emitAll('\n', 'cout << ', ' << '.join(args), ';')

    def enterTok(self, node:Tok):
        if   node.text =='NAME':    self.cout('NAME()')
        elif node.text =='NUMBER':  self.cout('NUMBER()')
        elif node.text =='STRING':  self.cout('STRING()')
        elif node.text =='NEWLINE': self.cout('endl')
        elif node.text =='INDENT':  self.emitAll('INDENT();', '\n')
        elif node.text =='DEDENT':  self.emitAll('DEDENT();', '\n')
        elif node.text == 'ENDMARKER': pass
        else: raise ValueError('unknown token:', node)

    def enterLit(self, node:Lit):
        self.cout('"%s"' % node.text)

    def enterRef(self, node:Ref):
        self.emitAll(node.text, '();')
        self.newline()

    def walkSeq(self, walk, node:Seq):
        self.between(walk, node.args, '\n')

    def walklist(self, walk, node:list):
        self.between(walk, node, '\n')

    def walkOpt(self, walk, node:Opt):
        self.emitAll('if (rand() % 2) {', INDENT)
        walk(node.args)
        self.emitAll(DEDENT, '}', '\n')

    def walkAlt(self, walk, node:Alt):
        self.emitAll('switch (rand() %% %i) {' % len(node.args), INDENT)
        for i, alt in enumerate(node.args):
            self.emitAll('\n', 'case ', str(i), ':', INDENT)
            walk(alt)
            self.emitAll(DEDENT, 'break;', '\n')
        self.emitAll(DEDENT, '}', '\n')

    def walkOrp(self, walk, node:Opt):
        pass


def gencpp():
    out = io.StringIO()
    out.write('\n'.join([
        '// ---- WARNING! this file is generated!! ---',
        '#include "genpy.hpp"',
        'using namespace std;',
        'namespace genpy {',
    ]))

    gram = meta.python_grammar()
    # function declarations
    for rule in gram.rules:
        out.write('void %s();\n' % rule.name)

    cpp = CPPEmitter()
    cpp.emitFn = out.write
    meta.GrammarWalker(cpp).walk(gram)

    out.write('\n'.join([
        '}',
        '//--- END OF GENERATED FILE ---',
        '']))
    return out.getvalue()

if __name__=="__main__":
    sys.stdout.write(gencpp())
