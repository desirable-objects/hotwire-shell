# This file is part of the Hotwire Shell project API.

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

import os, sys, unittest, tempfile, shutil, platform

import hotwire
from hotwire.command import HotwireContext
from hotwire.completion import *
from hotwire.builtins.cd import CdCompleter

class CompletionTestsUnix(unittest.TestCase):
    def setUp(self):
        self._tmpd = None
        self._context = HotwireContext()        

    def tearDown(self):
        if self._tmpd:
            shutil.rmtree(self._tmpd)
        self._context = None

    def _setupTree1(self):
        self._tmpd = tempfile.mkdtemp(prefix='hotwiretest')
        self._context.chdir(self._tmpd)
        testd = os.path.join(self._tmpd, 'testdir')
        os.mkdir(testd)
        open(os.path.join(self._tmpd, 'testf'), 'w').close()
        os.symlink(testd, os.path.join(self._tmpd, 'foolink'))

    def testCd1(self):
        self._setupTree1()
        cds = CdCompleter()
        results = list(cds.completions('test', self._tmpd))
        self.assertEquals(len(results), 1)
        self.assertEquals(results[0].target.path, os.path.join(self._tmpd, 'testdir'))
        self.assertEquals(results[0].suffix, 'dir/')
        
    def testCd2(self):
        self._setupTree1()
        cds = CdCompleter()        
        results = list(cds.completions('foo', self._tmpd))
        self.assertEquals(len(results), 1)        
        self.assertEquals(results[0].target.path, os.path.join(self._tmpd, 'foolink'))
        self.assertEquals(results[0].suffix, 'link/')
        
