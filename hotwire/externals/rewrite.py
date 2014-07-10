import parser
import token
import symbol
import sys

class _RewriteState(object):
    def __init__(self, output_func_name=None, output_func_self=None, print_func_name=None):
        self.mutated = []
        self.output_func_name = output_func_name
        self.output_func_self = output_func_self
        self.print_func_name = print_func_name

    def add_mutated(self, method_spec):
        if not method_spec in self.mutated:
            self.mutated.append(method_spec)

def _do_match(t, pattern):
    # Match an AST tree against a pattern. Along with symbol/token names, patterns
    # can contain strings:
    #
    #  '': ignore the matched item
    #  'name': store the matched item into the result dict under 'name'
    #  '*': matches items to the end of the sequence; ignore matched items
    #  '*name': matches items to the end of the sequence; store the matched items as a sequence into the result dict
    #
    # Things following '*" like ((token.LPAR, ''), '*', (token.RPAR, '')) are not currently
    # supported, but could be if needed
    #
    # Returns None if nothing matched or a dict of key/value pairs
    #
    if (t[0] != pattern[0]):
        return None
    
    result = {}
    for i in (xrange(1, len(pattern))):
        if i >= len(t):
            return None
        if isinstance(pattern[i], tuple):
            subresult = _do_match(t[i], pattern[i])
            if subresult == None:
                return None
            result.update(subresult)
        else:
            if pattern[i] == '':
                pass
            elif pattern[i][0] == '*':
                if pattern[i] != '*':
                    result[pattern[i][1:]] = t[i:]
            else:
                result[pattern[i]] = t[i]

    return result

if sys.version_info < (2, 5, 0):
    _method_call_pattern = \
                     (symbol.test,
                      (symbol.and_test,
                       (symbol.not_test,
                        (symbol.comparison,
                         (symbol.expr,
                          (symbol.xor_expr,
                           (symbol.and_expr,
                            (symbol.shift_expr,
                             (symbol.arith_expr,
                              (symbol.term,
                               (symbol.factor,
                                 
                                (symbol.power,
                                 (symbol.atom,
                                  (token.NAME, 'variable')),
                                 (symbol.trailer,
                                  (token.DOT, ''),
                                  (token.NAME, 'method')),
                                 (symbol.trailer,
                                  (token.LPAR, ''),
                                  '*')))))))))))))
else:
    _method_call_pattern = \
                     (symbol.test,
                      (symbol.or_test,
                       (symbol.and_test,
                        (symbol.not_test,
                         (symbol.comparison,
                          (symbol.expr,
                           (symbol.xor_expr,
                            (symbol.and_expr,
                             (symbol.shift_expr,
                              (symbol.arith_expr,
                               (symbol.term,
                                (symbol.factor,
                                 
                                 (symbol.power,
                                  (symbol.atom,
                                   (token.NAME, 'variable')),
                                  (symbol.trailer,
                                   (token.DOT, ''),
                                   (token.NAME, 'method')),
                                  (symbol.trailer,
                                   (token.LPAR, ''),
                                   '*'))))))))))))))

def _is_test_method_call(t):
    # Check if the given AST is a "test" of the form 'v.m()' If it
    # matches, returns { 'variable': 'v', "method": m }, otherwise returns None
    args = _do_match(t, _method_call_pattern)
    if args == None:
        return None
    else:
        return args['variable'], args['method']

if sys.version_info < (2, 5, 0):
    _attribute_pattern = \
                     (symbol.test,
                      (symbol.and_test,
                       (symbol.not_test,
                        (symbol.comparison,
                         (symbol.expr,
                          (symbol.xor_expr,
                           (symbol.and_expr,
                            (symbol.shift_expr,
                             (symbol.arith_expr,
                              (symbol.term,
                               (symbol.factor,
                                
                                (symbol.power,
                                 (symbol.atom,
                                  (token.NAME, 'variable')),
                                 (symbol.trailer,
                                  (token.DOT, ''),
                                  (token.NAME, ''))))))))))))))
else:
    _attribute_pattern = \
                     (symbol.test,
                      (symbol.or_test,
                       (symbol.and_test,
                        (symbol.not_test,
                         (symbol.comparison,
                          (symbol.expr,
                           (symbol.xor_expr,
                            (symbol.and_expr,
                             (symbol.shift_expr,
                              (symbol.arith_expr,
                               (symbol.term,
                                (symbol.factor,
                                 
                                 (symbol.power,
                                  (symbol.atom,
                                   (token.NAME, 'variable')),
                                  (symbol.trailer,
                                   (token.DOT, ''),
                                   (token.NAME, '')))))))))))))))
    
    
def _is_test_attribute(t):
    # Check if the given AST is a attribute of the form 'v.a' If it
    # matches, returns v, otherwise returns None
    args = _do_match(t, _attribute_pattern)
    
    if args == None:
        return None
    else:
        return args['variable']

if sys.version_info < (2, 5, 0):
    _slice_pattern = \
                     (symbol.test,
                       (symbol.and_test,
                        (symbol.not_test,
                         (symbol.comparison,
                          (symbol.expr,
                           (symbol.xor_expr,
                            (symbol.and_expr,
                             (symbol.shift_expr,
                              (symbol.arith_expr,
                               (symbol.term,
                                (symbol.factor,
                                 
                                 (symbol.power,
                                  (symbol.atom,
                                   (token.NAME, 'variable')),
                                  (symbol.trailer,
                                   (token.LSQB, ''),
                                   '*')))))))))))))
else:
    _slice_pattern = \
                     (symbol.test,
                      (symbol.or_test,
                       (symbol.and_test,
                        (symbol.not_test,
                         (symbol.comparison,
                          (symbol.expr,
                           (symbol.xor_expr,
                            (symbol.and_expr,
                             (symbol.shift_expr,
                              (symbol.arith_expr,
                               (symbol.term,
                                (symbol.factor,
                                 
                                 (symbol.power,
                                  (symbol.atom,
                                   (token.NAME, 'variable')),
                                  (symbol.trailer,
                                   (token.LSQB, ''),
                                   '*'))))))))))))))
    


def _is_test_slice(t):
    # Check if the given AST is a "test" of the form 'v[...]' If it
    # matches, returns v, otherwise returns None
    args = _do_match(t, _slice_pattern)

    if args == None:
        return None
    else:
        return args['variable']

if sys.version_info < (2, 5, 0):
    def _do_create_funccall_expr_stmt(name, trailer):
        return (symbol.expr_stmt,
                (symbol.testlist,
                 (symbol.test,
                  (symbol.and_test,
                   (symbol.not_test,
                    (symbol.comparison,
                     (symbol.expr,
                      (symbol.xor_expr,
                       (symbol.and_expr,
                        (symbol.shift_expr,
                         (symbol.arith_expr,
                          (symbol.term,
                           (symbol.factor,
                            (symbol.power,
                             (symbol.atom,
                              (token.NAME, name)),
                             trailer))))))))))))))
else:
    def _do_create_funccall_expr_stmt(name, trailer):
        return (symbol.expr_stmt,
                (symbol.testlist,
                 (symbol.test,
                  (symbol.or_test,
                   (symbol.and_test,
                    (symbol.not_test,
                     (symbol.comparison,
                      (symbol.expr,
                       (symbol.xor_expr,
                        (symbol.and_expr,
                         (symbol.shift_expr,
                          (symbol.arith_expr,
                           (symbol.term,
                            (symbol.factor,
                             (symbol.power,
                              (symbol.atom,
                               (token.NAME, name)),
                              trailer)))))))))))))))
    
def _create_funccall_expr_stmt(name, args):
    # Creates an 'expr_stmt' that calls a function. args is a list of
    # "test" AST's to pass as arguments to the function
    if len(args) == 0:
        trailer = (symbol.trailer,
                   (token.LPAR, '('),
                   (token.RPAR, ')'))
    else:
        arglist = [ symbol.arglist ]
        for a in args:
            if len(arglist) > 1:
                arglist.append((token.COMMA, ','))
            arglist.append((symbol.argument, a))
                
        trailer = (symbol.trailer,
                   (token.LPAR, ')'),
                   arglist,
                   (token.RPAR, ')'))

    return _do_create_funccall_expr_stmt(name, trailer)

def _create_varref(name):
    # I have to drop a note here that Python syntax trees are insane.
    return [symbol.test,
       [symbol.or_test,
        [symbol.and_test,
         [symbol.not_test,
          [symbol.comparison,
           [symbol.expr,
            [symbol.xor_expr,
             [symbol.and_expr,
              [symbol.shift_expr,
               [symbol.arith_expr,
                [symbol.term,
                 [symbol.factor, [symbol.power, [symbol.atom, [token.NAME, name]]]]]]]]]]]]]]]

def _rewrite_tree(t, state, actions):
    # Generic rewriting of an AST, actions is a map of symbol/token type to function
    # to call to produce a modified version of the the subtree
    result = t
    for i in xrange(1, len(t)):
        subnode = t[i]
        subtype = subnode[0]
        if actions.has_key(subtype):
            filtered = actions[subtype](subnode, state)
            if filtered != subnode:
                if result is t:
                    result = list(t)
                result[i] = filtered
                
    return result
        
def _rewrite_expr_stmt(t, state):
    # expr_stmt: testlist (augassign (yield_expr|testlist) |
    #                      ('=' (yield_expr|testlist))*)
    
    assert(t[0] == symbol.expr_stmt)
    assert(t[1][0] == symbol.testlist)
    
    if len(t) == 2:
        # testlist
        subnode = t[1]
        for i in xrange(1, len(subnode)):
            subsubnode = subnode[i]
            if subsubnode[0] == symbol.test:
                method_spec = _is_test_method_call(subsubnode)
                if (method_spec != None):
                    state.add_mutated(method_spec)

        if state.output_func_name != None:
            args = list(filter(lambda x: type(x) != int and x[0] == symbol.test, subnode))
            if state.output_func_self != None:
                args.insert(0, _create_varref(state.output_func_self))
            return _create_funccall_expr_stmt(state.output_func_name, tuple(args))
        else:
            return t
    else:
        if (t[2][0] == symbol.augassign):
            # testlist augassign (yield_expr|testlist)
            subnode = t[1]
            assert(len(subnode) == 2) # can only augassign one thing, despite the grammar
            
            variable = _is_test_slice(subnode[1])
            if variable == None:
                variable = _is_test_attribute(subnode[1])
            
            if variable != None:
                state.add_mutated(variable)
        else:
            # testlist ('=' (yield_expr|testlist))+
            for i in xrange(1, len(t) - 1):
                if (t[i + 1][0] == token.EQUAL):
                    subnode = t[i]
                    assert(subnode[0] == symbol.testlist)
                    for j in xrange(1, len(subnode)):
                        subsubnode = subnode[j]
                        if subsubnode[0] == symbol.test:
                            variable = _is_test_slice(subsubnode)
                            if variable == None:
                                variable = _is_test_attribute(subnode[1])
                                
                            if variable != None:
                                state.add_mutated(variable)
        return t

def _rewrite_print_stmt(t, state):
    # print_stmt: 'print' ( [ test (',' test)* [','] ] |
    #                       '>>' test [ (',' test)+ [','] ] )
    if state.print_func_name !=None and t[2][0] == symbol.test:
        return _create_funccall_expr_stmt(state.print_func_name, filter(lambda x: type(x) != int and x[0] == symbol.test, t))
    else:
        return t
    
def _rewrite_small_stmt(t, state):
    # small_stmt: (expr_stmt | print_stmt  | del_stmt | pass_stmt | flow_stmt |
    #              import_stmt | global_stmt | exec_stmt | assert_return)
    return _rewrite_tree(t, state,
                         { symbol.expr_stmt:  _rewrite_expr_stmt,
                           symbol.print_stmt: _rewrite_print_stmt })

    # Future special handling: import_stmt
    # Not valid: flow_stmt, global_stmt

def _rewrite_simple_stmt(t, state):
    # simple_stmt: small_stmt (';' small_stmt)* [';'] NEWLINE
    return _rewrite_tree(t, state,
                         { symbol.small_stmt: _rewrite_small_stmt })

def _rewrite_suite(t, state):
    # suite: simple_stmt | NEWLINE INDENT stmt+ DEDENT
    return _rewrite_tree(t, state,
                         { symbol.simple_stmt: _rewrite_simple_stmt,
                           symbol.stmt:        _rewrite_stmt })

def _rewrite_block_stmt(t, state):
    return _rewrite_tree(t, state,
                         { symbol.suite:      _rewrite_suite })

_rewrite_compound_stmt_actions = {
    symbol.if_stmt:    _rewrite_block_stmt,
    symbol.while_stmt: _rewrite_block_stmt,
    symbol.for_stmt:   _rewrite_block_stmt,
    symbol.try_stmt:   _rewrite_block_stmt,
}

if sys.version_info >= (2, 5, 0):
    # with statement is new in 2.5
    _rewrite_compound_stmt_actions[symbol.with_stmt] = _rewrite_block_stmt
    

def _rewrite_compound_stmt(t, state):
    # compound_stmt: if_stmt | while_stmt | for_stmt | try_stmt | with_stmt | funcdef | classdef
    return _rewrite_tree(t, state, _rewrite_compound_stmt_actions)

def _rewrite_stmt(t, state):
    # stmt: simple_stmt | compound_stmt
    return _rewrite_tree(t, state,
                         { symbol.simple_stmt:   _rewrite_simple_stmt,
                           symbol.compound_stmt: _rewrite_compound_stmt })

def _rewrite_file_input(t, state):
    # file_input: (NEWLINE | stmt)* ENDMARKER
    return _rewrite_tree(t, state, { symbol.stmt: _rewrite_stmt })

def rewrite_and_compile(code, output_func_name=None, output_func_self=None, print_func_name=None, encoding="utf8"):
    """
    Compiles the supplied text into code, while rewriting the parse tree so:

     * Print statements without a destination file are transformed into calls to
      <print_func_name>(*args), if print_func_name is not None
       
     * Statements which are simply expressions are transformed into calls to
       <output_func_name>(*args), if output_fnuc_name is not None
       (More than one argument is passed if the statement is in the form of a list; for example '1,2'.)

    At the same time, the code is scanned for possible mutations, and a list is returned.
    In the list:
    
      * A string indicates the mutation of a variable by assignment to a slice of it,
        or to an attribute.
    
      * A tuple of (variable_name, method_name) indicates the invocation of a method
        on the variable; this will sometimes be a mutation (e.g., list.append(value)),
        and sometimes not.
    """
    state = _RewriteState(output_func_name=output_func_name, output_func_self=output_func_self, print_func_name=print_func_name)

    if (isinstance(code, unicode)):
        code = code.encode("utf8")
        encoding = "utf8"
    
    original = parser.suite(code)
    rewritten = _rewrite_file_input(original.totuple(), state)
    encoded = (symbol.encoding_decl, rewritten, encoding)
    compiled = parser.sequence2ast(encoded).compile()

    return (compiled, state.mutated)
    

##################################################3

if __name__ == '__main__':
    def create_file_input(s):
        # Wrap up a statement (like an expr_stmt) into a file_input, so we can
        # parse/compile it
        return (symbol.file_input,
                (symbol.stmt,
                 (symbol.simple_stmt,
                  (symbol.small_stmt, s),
                  (token.NEWLINE, '\n'))),
                (token.ENDMARKER, '\n'))

    if sys.version_info < (2, 5, 0):
        def create_constant_test(c):
            # Create a test symbol which is a constant number
            return (symbol.test,
                    (symbol.and_test,
                     (symbol.not_test,
                      (symbol.comparison,
                       (symbol.expr,
                        (symbol.xor_expr,
                         (symbol.and_expr,
                          (symbol.shift_expr,
                           (symbol.arith_expr,
                            (symbol.term,
                             (symbol.factor,
                              (symbol.power,
                               (symbol.atom,
                                (token.NUMBER, str(c)))))))))))))))
    else:
        def create_constant_test(c):
            # Create a test symbol which is a constant number
            return (symbol.test,
                    (symbol.or_test,
                     (symbol.and_test,
                      (symbol.not_test,
                       (symbol.comparison,
                        (symbol.expr,
                         (symbol.xor_expr,
                          (symbol.and_expr,
                           (symbol.shift_expr,
                            (symbol.arith_expr,
                             (symbol.term,
                              (symbol.factor,
                               (symbol.power,
                                (symbol.atom,
                                 (token.NUMBER, str(c))))))))))))))))
            

    #
    # Test _create_funccall_expr_stmt
    # 

    def test_funccall(args):
        t = create_file_input(_create_funccall_expr_stmt('set_test_args',
                                                         map(lambda c: create_constant_test(c), args)))
        test_args = [ 'UNSET' ]
        def set_test_args(*args): test_args[:] = args
        scope = { 'set_test_args': set_test_args }
        
        exec parser.sequence2ast(t).compile() in scope
        assert tuple(test_args) == args

    test_funccall(())
    test_funccall((1,))
    test_funccall((1,2))

    #
    # Test that our intercepting of bare expressions to save the output works
    #
    def test_output(code, expected):
        compiled, _ = rewrite_and_compile(code, output_func_name='reinteract_output')
        
        test_args = []
        def set_test_args(*args):
            test_args[:] = args
        scope = { 'reinteract_output': set_test_args} 

        exec compiled in scope

        if tuple(test_args) != tuple(expected):
            raise AssertionError("Got '%s', expected '%s'" % (test_args, expected))

    test_output('a=3', ())
    test_output('1', (1,))
    test_output('1,2', (1,2))
    test_output('1;2', (2,))
    test_output('a=3; a', (3,))
    
    # Now pass in a "self" value
    def test_output_self(code, expected):
        compiled, _ = rewrite_and_compile(code, output_func_name='reinteract_output', output_func_self='reinteract_output_self')
        
        test_self = {}
        def set_test_args(myself, *args):
            myself['args'] = args
        scope = { 'reinteract_output': set_test_args, 
                  'reinteract_output_self': test_self} 

        exec compiled in scope

        if 'args' not in test_self:
            raise AssertionError("Failed to set arguments")
        if tuple(test_self['args']) != tuple(expected):
            raise AssertionError("Got '%s', expected '%s'" % (test_args, expected))

    test_output_self('1', (1,))
    test_output_self('1,2', (1,2))
    test_output_self('1;2', (2,))   
    test_output_self('a=3; a', (3,))

    #
    # Test that our intercepting of print works
    #
    def test_print(code, expected):
        compiled, _ = rewrite_and_compile(code, print_func_name='reinteract_print')
        
        test_args = []
        def set_test_args(*args): test_args[:] = args
        scope = { 'reinteract_print': set_test_args }

        exec compiled in scope

        if tuple(test_args) != tuple(expected):
            raise AssertionError("Got '%s', expected '%s'" % (test_args, expected))

    test_print('a=3', ())
    test_print('print 1', (1,))
    test_print('print 1,2', (1,2))
    test_print('print "",', ("",))
    test_print('for i in [0]: print i', (0,))
    test_print('import sys; print >>sys.stderr, "",', ())

    #
    # Test catching possible mutations of variables
    #
    def test_mutated(code, expected):
        _, mutated = rewrite_and_compile(code)

        mutated = list(mutated)
        mutated.sort()
        
        expected = list(expected)
        expected.sort()

        if tuple(mutated) != tuple(expected):
            raise AssertionError("Got '%s', expected '%s'" % (mutated, expected))

    test_mutated('a[0] = 1', ('a',))
    test_mutated('a[0], b[0] = 1, 2', ('a', 'b'))
    test_mutated('a[0], _ = 1', ('a'))
    test_mutated('a[0], b[0] = c[0], d[0] = 1, 2', ('a', 'b', 'c', 'd'))

    test_mutated('a[0] += 1', ('a',))
    
    test_mutated('a.b = 1', ('a',))
    test_mutated('a.b += 1', ('a',))
    
    test_mutated('a.b()', (('a','b'),))
    test_mutated('a.b(1,2)', (('a','b'),))
    test_mutated('a.b.c(1,2)', ())

    #
    # Test handling of encoding
    #
    def test_encoding(code, expected, encoding=None):
        if encoding != None:
            compiled, _ = rewrite_and_compile(code, encoding=encoding, output_func_name='reinteract_output')
        else:
            compiled, _ = rewrite_and_compile(code, output_func_name='reinteract_output')
        
        test_args = []
        def set_test_args(*args): test_args[:] = args
        scope = { 'reinteract_output': set_test_args }

        exec compiled in scope

        if test_args[0] != expected:
            raise AssertionError("Got '%s', expected '%s'" % (test_args[0], expected))

    test_encoding(u"u'\u00e4'".encode("utf8"), u'\u00e4')
    test_encoding(u"u'\u00e4'", u'\u00e4')
    test_encoding(u"u'\u00e4'".encode("iso-8859-1"), u'\u00e4', "iso-8859-1")

    print "Passed"