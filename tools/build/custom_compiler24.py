#!/usr/bin/python2.4

import sys
import compiler
import compiler.syntax
import compiler.misc
from compiler.pycodegen import Module as PyCodeGenModule


class DiaDocStringScrubVisitor(compiler.visitor.ASTVisitor):
    def __init__(self):
        compiler.visitor.ASTVisitor.__init__(self)

    def default(self, node, *args):
        if getattr(node, "doc", None):
            if isinstance(node.doc, str) and len(node.doc.strip()) != 0:
                node.doc = ''
        compiler.visitor.ASTVisitor.default(self, node, *args)


class VisitingCompiler(PyCodeGenModule):
    def __init__(self, source, filename, visitor):
        PyCodeGenModule.__init__(self, source, filename)
        self.visitor = visitor

    def _get_tree(self):
        tree = compiler.parse(self.source)
        compiler.walk(tree, self.visitor, walker=self.visitor)
        compiler.misc.set_filename(self.filename, tree)
        compiler.syntax.check(tree)
        return tree


def compile(file, cfile, doraise=False):
    visitor = DiaDocStringScrubVisitor()
    f = open(file, 'U')
    buf = f.read()
    f.close()
    mod = VisitingCompiler(buf, file, visitor)
    try:
        mod.compile()
    except SyntaxError:
        if doraise:
            raise
        else:
            pass
    else:
        f = open(cfile, "wb")
        mod.dump(f)
        f.close()


