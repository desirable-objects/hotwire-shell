# This file is part of the Hotwire Shell project API.
# -*- coding: utf-8 -*-

# Copyright (C) 2007 Colin Walters <walters@verbum.org>

# Permission is hereby granted, free of charge, to any person obtaining a copy 
# of this software and associated documentation files (the "Software"), to deal 
# in the Software without restriction, including without limitation the rights 
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies 
# of the Software, and to permit persons to whom the Software is furnished to do so, 
# subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all 
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE X CONSORTIUM BE 
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, 
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR 
# THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import os, sys, unittest, tempfile, shutil

import hotwire
from hotwire.command import *
from hotwire.sysdep import is_windows, is_unix
from hotwire.sysdep.fs import File
import hotwire.script
from hotwire.fs import unix_basename, path_join, path_abs, path_dirname, path_fastnormalize

class PipelineParserTests(unittest.TestCase):
    def setUp(self):
        self._context = HotwireContext()

    def tearDown(self):
        self._context = None
    
    def testEmacs(self):
        pt = list(Pipeline.tokenize('emacs', self._context, assertfn=self.assertEquals))
        self.assertEquals(len(pt), 1)
        self.assertEquals(pt[0].text, 'emacs')

    def testEmacsFile(self):
        pt = list(Pipeline.tokenize('emacs /tmp/foo.txt', self._context, assertfn=self.assertEquals))
        self.assertEquals(len(pt), 2)
        self.assertEquals(pt[0].text, 'emacs')
        self.assertEquals(pt[1].text, '/tmp/foo.txt')
        self.assertEquals(pt[1].quoted, False) 

    def testEmacsFileSpace(self):
        pt = list(Pipeline.tokenize("emacs 'foo bar'", self._context, assertfn=self.assertEquals))
        self.assertEquals(len(pt), 2)
        self.assertEquals(pt[0].text, 'emacs')
        self.assertEquals(pt[1].text, "foo bar")
        self.assertEquals(pt[1].quoted, True)        

    def testEmacsFileSpaces(self):
        pt = list(Pipeline.tokenize("emacs 'foo bar' baz 'whee cow crack'", self._context, assertfn=self.assertEquals))
        self.assertEquals(len(pt), 4)
        self.assertEquals(pt[0].text, 'emacs')
        self.assertEquals(pt[1].text, "foo bar")
        self.assertEquals(pt[2].text, "baz")
        self.assertEquals(pt[3].text, "whee cow crack")
        self.assertEquals(pt[3].quoted, True)

    def testLsMulti(self):
        pt = list(Pipeline.tokenize('ls foo.py bar.py baz.py', self._context, assertfn=self.assertEquals))
        self.assertEquals(len(pt), 4)

    def testMulti(self):
        pt = list(Pipeline.tokenize('sys echo true | sys cat /tmp/foo.txt', self._context))
        self.assertEquals(len(pt), 7)
        self.assertEquals(pt[3], hotwire.script.PIPE)

    def testMulti4(self):
        pt = list(Pipeline.tokenize('sys echo true | sys cat /tmp/foo.txt | sys echo moo  cow | sys cat cat cat /tmp/foo.txt', self._context))
        self.assertEquals(len(pt), 18)

    def testPathological1(self):
        pt = list(Pipeline.tokenize('cat | ls', self._context))
        self.assertEquals(len(pt), 3)
        
    def testNoSpace1(self):
        pt = list(Pipeline.tokenize('cat|sys echo bar', self._context))
        self.assertEquals(len(pt), 5)
        self.assertEquals(pt[0].text, 'cat')
        self.assertEquals(pt[1], hotwire.script.PIPE)
        
    def testNull(self):
        pt = list(Pipeline.tokenize('', self._context))
        self.assertEquals(len(pt), 0)
        
    def testGlob1(self):
        pt = list(Pipeline.tokenize('echo f*', self._context))
        self.assertEquals(len(pt), 2)
        
    def testRedir1(self):
        pt = list(Pipeline.tokenize('echo f>bar', self._context))
        self.assertEquals(len(pt), 4)
        self.assertEquals(pt[2], hotwire.script.REDIR_OUT)
        
    def testOtherChars1(self):
        pt = list(Pipeline.tokenize('env f=b true', self._context))
        self.assertEquals(len(pt), 3)   
        
    def testUtf1(self):
        pt = list(Pipeline.tokenize('sys echo Ω', self._context))
        self.assertEquals(len(pt), 3)
        self.assertEquals(pt[2].text, 'Ω')
        self.assertEquals(pt[2].quoted, False)
        
    def testUtf2(self):
        pt = list(Pipeline.tokenize('sys echo "Ω"', self._context))
        self.assertEquals(len(pt), 3)
        self.assertEquals(pt[2].text, 'Ω')
        self.assertEquals(pt[2].quoted, True)
        
    def testBracket1(self):
        pt = list(Pipeline.tokenize('echo f>bar{baz}', self._context))
        self.assertEquals(len(pt), 4)
        self.assertEquals(pt[3].text, 'bar{baz}')
        
    def testParens1(self):
        pt = list(Pipeline.tokenize('echo foo(bar)', self._context))
        self.assertEquals(len(pt), 2)
        self.assertEquals(pt[1].text, 'foo(bar)')
        
    def testDollar1(self):
        pt = list(Pipeline.tokenize('echo $foo', self._context))
        self.assertEquals(len(pt), 2)
        self.assertEquals(pt[1].text, '$foo')  
        
    def testAt1(self):
        pt = list(Pipeline.tokenize('echo foo@bar', self._context))
        self.assertEquals(len(pt), 2)
        self.assertEquals(pt[1].text, 'foo@bar')

class PipelineInstantiateTests(unittest.TestCase):
    def setUp(self):
        self._context = HotwireContext()

    def tearDown(self):
        self._context = None

    def testSh(self):
        p = Pipeline.parse('sys echo true', self._context)
        self.assertEquals(p.get_input_type(), str)
        self.assertEquals(p.get_output_type(), str)
        self.assertEquals(p.get_undoable(), False)
        self.assertEquals(p.get_idempotent(), False)

    def testShFilter(self):
        p = Pipeline.parse('sys echo true | filter true', self._context)
        self.assertEquals(p.get_input_type(), str)
        self.assertEquals(p.get_output_type(), str)
        self.assertEquals(p.get_undoable(), False)
        self.assertEquals(p.get_idempotent(), False)

    def testPs(self):
        p = Pipeline.parse('proc', self._context)
        self.assertEquals(p.get_input_type(), None)
        self.assertEquals(p.get_output_type(), hotwire.sysdep.proc.Process)
        self.assertEquals(p.get_undoable(), False)
        self.assertEquals(p.get_idempotent(), True)

    def testMv(self):
        p = Pipeline.parse('mv foo bar', self._context)
        self.assertEquals(p.get_input_type(), None)
        self.assertEquals(p.get_output_type(), None)
        self.assertEquals(p.get_undoable(), False)
        self.assertEquals(p.get_idempotent(), False)

    def testRm(self):
        p = Pipeline.parse('rm foo bar', self._context)
        self.assertEquals(p.get_input_type(), File)
        self.assertEquals(p.get_output_type(), None)
        self.assertEquals(p.get_undoable(), True)
        self.assertEquals(p.get_idempotent(), False)

    def testInvalid1(self):
        self.assertRaises(hotwire.command.PipelineParseException, lambda: Pipeline.parse('mv foo bar | sys cat', self._context))

    def testInvalid2(self):
        self.assertRaises(hotwire.command.PipelineParseException, lambda: Pipeline.parse('sys cat | proc', self._context))

    def testInvalid3(self):
        self.assertRaises(hotwire.command.PipelineParseException, lambda: Pipeline.parse('filter foo', self._context))

    def testInvalid4(self):
        self.assertRaises(hotwire.command.PipelineParseException, lambda: Pipeline.parse('ls | cd test', self._context))

    def testInvalidArgCount1(self):
        self.assertRaises(hotwire.command.PipelineParseException, lambda: Pipeline.parse('fsearch', self._context))
        
    def testInvalidOptions1(self):
        self.assertRaises(hotwire.command.PipelineParseException, lambda: Pipeline.parse('fsearch --frob', self._context))
        self.assertRaises(hotwire.command.PipelineParseException, lambda: Pipeline.parse('fsearch -x', self._context))                 

class PipelineRunTestFramework(unittest.TestCase):
    def setUp(self):
        self._context = HotwireContext()
        self._tmpd = tempfile.mkdtemp(prefix='hotwiretest')
        self._tmpd = path_fastnormalize(self._tmpd)
        self._context.chdir(self._tmpd)

    def tearDown(self):
        self._context = None
        shutil.rmtree(unicode(self._tmpd))

    def _setupTree1(self):
        os.mkdir(path_join(self._tmpd, 'testdir'))
        open(path_join(self._tmpd, 'testf'), 'w').close()
        os.mkdir(path_join(self._tmpd, 'dir with spaces'))

    def _setupTree2(self):
        self._setupTree1()
        open(path_join(self._tmpd, 'testf2'), 'w').close()
        open(path_join(self._tmpd, 'f3test'), 'w').close()
        open(path_join(self._tmpd, 'otherfile'), 'w').close()
        os.mkdir(path_join(self._tmpd, 'testdir2'))
        open(path_join(self._tmpd, 'testdir2', 'blah'), 'w').close()


class PipelineRunTests(PipelineRunTestFramework):
    def testPs(self):
        p = Pipeline.parse('proc', self._context)
        p.execute_sync()

    def testPsFilter(self):
        p = Pipeline.parse('proc | filter python cmd', self._context)
        p.execute()
        found_objs = False
        for obj in p.get_output(): 
            found_objs = True
            break
        self.assert_(found_objs)

    def testPsFilter2(self):
        p = Pipeline.parse('proc | filter this-command-does-not-exist cmd', self._context)
        p.execute()
        found_objs = False
        for obj in p.get_output(): 
            found_objs = True
            break
        self.assert_(not found_objs)

    def testRm(self):
        self._setupTree1()
        testf_path = path_join(self._tmpd, 'testf') 
        self.assertEquals(os.access(testf_path, os.R_OK), True)
        p = Pipeline.parse('rm testf', self._context)
        p.execute_sync()
        self.assertEquals(os.access(testf_path, os.R_OK), False)

    def testRm2(self):
        self._setupTree1()
        testf_path = path_join(self._tmpd, 'testf') 
        self.assertEquals(os.access(testf_path, os.R_OK), True)
        p = Pipeline.parse('rm %s' % (testf_path,), self._context)
        p.execute_sync()
        self.assertEquals(os.access(testf_path, os.R_OK), False)

    def testRm3(self):
        self._setupTree2()
        p = Pipeline.parse('rm test* f3test', self._context)
        p.execute_sync()
        self.assertEquals(os.access(path_join(self._tmpd, 'testdir'), os.R_OK), False)
        self.assertEquals(os.access(path_join(self._tmpd, 'testf'), os.R_OK), False)
        self.assertEquals(os.access(path_join(self._tmpd, 'testf2'), os.R_OK), False)
        self.assertEquals(os.access(path_join(self._tmpd, 'f3test'), os.R_OK), False)
        self.assertEquals(os.access(path_join(self._tmpd, 'otherfile'), os.R_OK), True)

    def testRm4(self):
        self._setupTree2()
        p = Pipeline.parse('rm %s %s' % (path_join(self._tmpd, 'f3test'), path_join(self._tmpd, 'otherfile')),
                           self._context)
        p.execute_sync()
        self.assertEquals(os.access(path_join(self._tmpd, 'testf'), os.R_OK), True)
        self.assertEquals(os.access(path_join(self._tmpd, 'f3test'), os.R_OK), False)
        self.assertEquals(os.access(path_join(self._tmpd, 'otherfile'), os.R_OK), False)

    def testRm5(self):
        self._setupTree1()
        p = Pipeline.parse('rm testf', self._context)
        p.execute_sync()
        self.assertEquals(os.access(path_join(self._tmpd, 'testf'), os.R_OK), False)
        open(path_join(self._tmpd, 'testf'), 'w').close()
        self.assertEquals(os.access(path_join(self._tmpd, 'testf'), os.R_OK), True)
        p = Pipeline.parse('rm testf', self._context)
        p.execute_sync()
        self.assertEquals(os.access(path_join(self._tmpd, 'testf'), os.R_OK), False)

    def testRm6(self):
        self._setupTree1()
        self.assertEquals(os.access(path_join(self._tmpd, 'dir with spaces'), os.R_OK), True)
        p = Pipeline.parse("rm 'dir with spaces'", self._context)
        p.execute_sync()
        self.assertEquals(os.access(path_join(self._tmpd, 'dir with spaces'), os.R_OK), False)

    def testRm7(self):
        self._setupTree1()
        testf_path = path_join(self._tmpd, 'testf') 
        self.assertEquals(os.access(testf_path, os.R_OK), True)
        p = Pipeline.parse('rm testf', self._context)
        p.execute_sync()
        self.assertEquals(os.access(testf_path, os.R_OK), False)
        p.undo()
        self.assertEquals(os.access(testf_path, os.R_OK), True)
        
    def testRm8(self):
        self._setupTree2()
        self.assertEquals(os.access(path_join(self._tmpd, 'testf'), os.R_OK), True)
        self.assertEquals(os.access(path_join(self._tmpd, 'f3test'), os.R_OK), True)               
        p = Pipeline.parse('ls testf f3test | rm --unlink', self._context)
        p.execute_sync()
        self.assertEquals(os.access(path_join(self._tmpd, 'testf'), os.R_OK), False)
        self.assertEquals(os.access(path_join(self._tmpd, 'f3test'), os.R_OK), False)
        
    def testRm9(self):
        self._setupTree1()
        t = path_join(self._tmpd, '--frob')
        f = open(t, 'w')
        f.write('hi')
        f.close()
        self.assertEquals(os.access(t, os.R_OK), True)        
        p = Pipeline.parse('rm --unlink -- --frob', self._context)
        p.execute_sync()
        self.assertEquals(os.access(t, os.R_OK), False)

    def testMv(self):
        self._setupTree2()
        p = Pipeline.parse('mv testf testdir', self._context)
        p.execute_sync()
        self.assertEquals(os.access(path_join(self._tmpd, 'testf'), os.R_OK), False)
        self.assertEquals(os.access(path_join(self._tmpd, 'testdir', 'testf'), os.R_OK), True)

    def testMv2(self):
        self._setupTree2()
        p = Pipeline.parse('mv testf testdir', self._context)
        p.execute_sync()
        p = Pipeline.parse('mv testdir testdir2', self._context)
        p.execute_sync()
        self.assertEquals(os.access(path_join(self._tmpd, 'testf'), os.R_OK), False)
        self.assertEquals(os.access(path_join(self._tmpd, 'testdir'), os.R_OK), False)
        self.assertEquals(os.access(path_join(self._tmpd, 'testdir2', 'testdir', 'testf'), os.R_OK), True)

    def testCd(self):
        self._setupTree1()
        oldwd = self._context.get_cwd()
        p = Pipeline.parse('cd testdir', self._context)
        p.execute_sync()
        self.assertEquals(self._context.get_cwd(), path_abs(path_join(oldwd, 'testdir')))

    def testLs(self):
        self._setupTree1()
        p = Pipeline.parse("ls *test*", self._context)
        p.execute_sync()
        results = list(p.get_output())
        results.sort()
        self.assertEquals(len(results), 2)
        self.assertEquals(os.path.dirname(results[0].path), self._tmpd)
        self.assertEquals(unix_basename(results[0].path), 'testdir')
        self.assertEquals(os.path.dirname(results[1].path), self._tmpd)
        self.assertEquals(unix_basename(results[1].path), 'testf')

    def testLs2(self):
        p = Pipeline.parse("ls ~", self._context)
        p.execute_sync()

    def testLs3(self):
        self._setupTree1()
        p = Pipeline.parse("ls testdir", self._context)
        p.execute_sync()
        results = list(p.get_output())
        self.assertEquals(len(results), 0)

    def testLs4(self):
        self._setupTree1()
        p = Pipeline.parse("ls | filter spac path", self._context)
        p.execute_sync()
        results = list(p.get_output())
        self.assertEquals(len(results), 1)
        self.assertEquals(os.path.dirname(results[0].path), self._tmpd)
        self.assertEquals(unix_basename(results[0].path), 'dir with spaces')
        
    def testLs5(self):
        self._setupTree2()
        p = Pipeline.parse("ls testdir2/b*", self._context)
        p.execute_sync()
        results = list(p.get_output())
        self.assertEquals(len(results), 1)   
        
    def testLs6(self):
        self._setupTree1()
        p = Pipeline.parse("ls testf", self._context)
        p.execute_sync()
        results = list(p.get_output())
        results.sort()
        self.assertEquals(len(results), 1)
        self.assertEquals(os.path.dirname(results[0].path), self._tmpd)
        self.assertEquals(unix_basename(results[0].path), 'testf')                     

    def testLsQuoted(self):
        self._setupTree1()
        hidden = path_join(self._tmpd, "foo'bar")
        open(hidden, 'w').close()
        p = Pipeline.parse("ls \"foo'bar\"", self._context)
        p.execute_sync()
        results = list(p.get_output())
        self.assertEquals(len(results), 1)

    def testCdQuoted(self):
        self._setupTree1()
        p = path_join(self._tmpd, "foo'bar")
        os.mkdir(p)
        p = Pipeline.parse("cd \"foo'bar\"", self._context)
        p.execute_sync()
        results = list(p.get_output())
        self.assertEquals(len(results), 0)

    def testCdQuoted2(self):
        if is_windows():
            # The double quote " apparently is not valid in file names on NTFS.  
            # Just don't run this test then.
            return
        self._setupTree1()
        p = path_join(self._tmpd, "foo\"bar")
        os.mkdir(p)
        p = Pipeline.parse("cd 'foo\"bar'", self._context)
        p.execute_sync()
        results = list(p.get_output())
        self.assertEquals(len(results), 0)

    def testCp(self):
        self._setupTree2()
        self.assertEquals(os.access(path_join(self._tmpd, 'testf3'), os.R_OK), False)
        p = Pipeline.parse('cp testf testf3', self._context)
        p.execute_sync()
        self.assertEquals(os.access(path_join(self._tmpd, 'testf'), os.R_OK), True)
        self.assertEquals(os.access(path_join(self._tmpd, 'testf3'), os.R_OK), True)
        
    def testCp2(self):
        self._setupTree2()
        self.assertEquals(os.access(path_join(self._tmpd, 'testdir', 'testf'), os.R_OK), False)
        p = Pipeline.parse('cp testf testdir', self._context)
        p.execute_sync()
        self.assertEquals(os.access(path_join(self._tmpd, 'testf'), os.R_OK), True)
        self.assertEquals(os.access(path_join(self._tmpd, 'testdir', 'testf'), os.R_OK), True)

    def testCp3(self):
        self._setupTree2()
        p = Pipeline.parse('cp testf testdir2/blah', self._context)
        p.execute_sync()
        self.assertEquals(os.access(path_join(self._tmpd, 'testdir2', 'blah'), os.R_OK), True)

    def testCp4(self):
        self._setupTree2()
        p = Pipeline.parse('cp testdir2 testdir3', self._context)
        p.execute_sync()
        self.assertEquals(os.access(path_join(self._tmpd, 'testdir3', 'blah'), os.R_OK), True)

    def testCp5(self):
        self._setupTree2()
        p = Pipeline.parse('cp testf \'dir with spaces\' testdir2', self._context)
        p.execute_sync()
        self.assertEquals(os.access(path_join(self._tmpd, 'testdir2', 'testf'), os.R_OK), True)
        self.assertEquals(os.access(path_join(self._tmpd, 'testdir2', 'dir with spaces'), os.R_OK), True)
        
    def testRedir1(self):
        self._setupTree2()
        p = Pipeline.parse("ls testdir2 | prop path > outtest.txt", self._context)
        p.execute_sync()
        outpath = path_join(self._tmpd, 'outtest.txt')
        self.assertEquals(os.access(outpath, os.R_OK), True)
        lines = list(open(outpath))
        self.assertEquals(len(lines), 1)
        self.assertEquals(lines[0], path_join(self._tmpd, 'testdir2', 'blah'))
        
    def testRedir2(self):
        self._setupTree2()
        outpath = path_join(self._tmpd, 'sectest.txt')
        f= open(outpath, 'wb')
        f.write('hello world\n')
        f.write('sha test\n')        
        f.close()
        p = Pipeline.parse("sechash < sectest.txt", self._context)
        p.execute_sync()
        results = list(p.get_output())
        self.assertEquals(len(results), 2)
        self.assertEquals(results[0], '22596363b3de40b06f981fb85d82312e8c0ed511')
        self.assertEquals(results[1], '84b5d4093c8ffaf2eca0feaf014a53b9f41d28ed')
        
    def testCat1(self):
        self._setupTree2()
        outpath = path_join(self._tmpd, 'cattest.txt')
        f= open(outpath, 'wb')
        f.write('hello world\n')       
        f.close()
        p = Pipeline.parse("cat cattest.txt", self._context)
        p.execute_sync()
        results = list(p.get_output())
        self.assertEquals(len(results), 1)
        self.assertEquals(results[0], 'hello world\n')    
        
    def testWrite1(self):
        self._setupTree1()
        p = Pipeline.parse("ls | py-map 'it.path+\"\\n\"' | write outtest.txt", self._context)
        p.execute_sync()
        outpath = path_join(self._tmpd, 'outtest.txt')
        self.assertEquals(os.access(outpath, os.R_OK), True)
        lines = list(open(outpath))
        self.assertEquals(len(lines), 3)
        
    def testNewlineAndWrite1(self):
        self._setupTree1()
        p = Pipeline.parse("ls|prop path|newline|write outtest.txt", self._context)
        p.execute_sync()
        outpath = path_join(self._tmpd, 'outtest.txt')
        self.assertEquals(os.access(outpath, os.R_OK), True)
        lines = list(open(outpath))
        self.assertEquals(len(lines), 3)
        
    def testNewline2(self):
        self._setupTree1()
        p = Pipeline.parse("py-eval '[\"hello\\n\", \"world\"]' | iter | newline", self._context)
        p.execute_sync()
        results = list(p.get_output())
        self.assertEquals(len(results), 2)
        
    def testFilter1(self):
        self._setupTree1()
        p = Pipeline.parse("py-eval 20 | filter -s 2", self._context)
        p.execute_sync()
        results = list(p.get_output())
        self.assertEquals(len(results), 1)
        self.assertEquals(results[0], 20)
        
    def testFilter2(self):
        self._setupTree1()
        p = Pipeline.parse("py-eval '\"hello\"' | filter h", self._context)
        p.execute_sync()
        results = list(p.get_output())
        self.assertEquals(len(results), 1)
        self.assertEquals(results[0], 'hello')
        
    def testUtf1(self):
        self._setupTree1()
        opath = os.path.join(self._tmpd, u'the ɒ and Ω ends')
        f=open(opath, 'w')
        f.write('hi')
        f.close()        
        opath = os.path.join(self._tmpd, u'ending with Ω back to the ɒ')        
        f=open(opath, 'w')
        f.write('hi')
        f.close()
        p = Pipeline.parse('ls *Ω*', self._context)
        p.execute_sync()
        results = list(p.get_output())
        self.assertEquals(len(results), 2)
        self.assertEquals(results[0].basename, 'ending with Ω back to the ɒ')
        self.assertEquals(results[1].basename, 'the ɒ and Ω ends')
        
    def testStringify1(self):
        self._setupTree1()
        p = Pipeline.parse("py-eval '\"hello\"' | stringify", self._context)
        p.execute_sync()
        results = list(p.get_output())
        self.assertEquals(len(results), 1)
        self.assertEquals(results[0], 'hello')
        
    def testStringify2(self):
        self._setupTree1()
        p = Pipeline.parse("py-eval 20 | stringify", self._context)
        p.execute_sync()
        results = list(p.get_output())
        self.assertEquals(len(results), 1)
        self.assertEquals(results[0], '20')
        
    def testStringify3(self):
        self._setupTree1()
        p = Pipeline.parse("py-eval 'import os,sys; [os,sys]' | iter | stringify", self._context)
        p.execute_sync()
        results = list(p.get_output())
        self.assertEquals(len(results), 2)
        self.assertTrue(results[0].startswith("<module 'os'"))
        self.assertTrue(results[1].startswith("<module 'sys'"))
        
    def testApply1(self):
        self._setupTree1()
        p = Pipeline.parse("py-eval '\"testf\"' | apply ls -a", self._context)
        p.execute_sync()
        results = list(p.get_output())
        self.assertEquals(len(results), 1)
        self.assertEquals(results[0].basename, u'testf')
        
    def testSyncException(self):
        self._setupTree1()
        p = Pipeline.parse("py-eval 'None+2'", self._context)
        self.assertRaises(TypeError, p.execute_sync)
        
    def testPyEvalSingle(self):
        self._setupTree1()
        p = Pipeline.parse("py-eval '42'", self._context)
        self.assertTrue(p.is_singlevalue)
        
    def testSetEnv1(self):
        self._setupTree1()
        self.assertTrue('HOTWIRETESTVALUE42' not in os.environ)
        p = Pipeline.parse("setenv HOTWIRETESTVALUE42=blah", self._context)
        p.execute_sync()
        self.assertTrue('HOTWIRETESTVALUE42' in os.environ)
        del os.environ['HOTWIRETESTVALUE42']

    def testSort1(self):
        self._setupTree1()
        p = Pipeline.parse("py-eval '[5,2,7,8,10,0]' | iter | sort")
        p.execute_sync()
        results = list(p.get_output())
        self.assertEquals([0,2,5,7,8,10], results)

    def testUniq1(self):
        self._setupTree1()
        p = Pipeline.parse("py-eval '[1,1,2,4,5,4]' | iter | uniq")
        p.execute_sync()
        results = list(p.get_output())
        self.assertEquals([1,2,4,5], results)

    def testHead1(self):
        self._setupTree1()
        p = Pipeline.parse("py-eval '[5,2,7,8,10,0,34]' | iter | head -5")
        p.execute_sync()
        results = list(p.get_output())
        self.assertEquals([5,2,7,8,10], results)

        
def suite():
    loader = unittest.TestLoader()
    loader.loadTestsFromTestCase(PipelineParserTests)
    
    suite.addTest(PipelineParserTests())
    suite.addTest(PipelineInstantiateTests())
    return suite
