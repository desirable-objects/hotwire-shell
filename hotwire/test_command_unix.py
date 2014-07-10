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

import os,sys,time

import hotwire
from hotwire.command import *
from hotwire.test_command import PipelineRunTestFramework
from hotwire.fs import unix_basename, path_join

class PipelineRunTestsUnix(PipelineRunTestFramework):
    def testSh(self):
        self._setupTree1()
        self.assertEquals(os.access(os.path.join(self._tmpd, 'otherfile'), os.R_OK), False)
        p = Pipeline.parse('sys touch otherfile', self._context)
        p.execute_sync()
        self.assertEquals(os.access(os.path.join(self._tmpd, 'otherfile'), os.R_OK), True)

    def testSh2(self):
        self._setupTree1()
        self.assertEquals(os.access(os.path.join(self._tmpd, 'file with spaces'), os.R_OK), False)
        p = Pipeline.parse('sys touch "file with spaces"', self._context)
        p.execute_sync()
        self.assertEquals(os.access(os.path.join(self._tmpd, 'file with spaces'), os.R_OK), True)

    def testSh3(self):
        self._setupTree2()
        self.assertEquals(os.access(os.path.join(self._tmpd, 'dir with spaces'), os.R_OK), True)
        p = Pipeline.parse("sys rmdir 'dir with spaces'", self._context)
        p.execute_sync()
        self.assertEquals(os.access(os.path.join(self._tmpd, 'dir with spaces'), os.R_OK), False)

    def testSh4(self):
        self._setupTree1()
        p = Pipeline.parse("sys ls -1 -d *test*", self._context)
        p.execute_sync()
        results = list(p.get_output())
        results.sort()
        self.assertEquals(len(results), 2)
        self.assertEquals(results[0], 'testdir\n')
        self.assertEquals(results[1], 'testf\n')

    def testSh5(self):
        self._setupTree1()
        p = Pipeline.parse("sys ls -1 -d *test* | filter dir", self._context)
        p.execute_sync()
        results = list(p.get_output())
        results.sort()
        self.assertEquals(len(results), 1)
        self.assertEquals(results[0], 'testdir\n')

    def testShCancel1(self):
        p = Pipeline.parse("sys sleep 5", self._context)
        p.execute()
        p.cancel()
        results = list(p.get_output())
        self.assertEquals(len(results), 0)

    def testShCancel2(self):
        p = Pipeline.parse("sys sleep 6", self._context)
        p.execute()
        time.sleep(2)
        p.cancel()
        results = list(p.get_output())
        self.assertEquals(len(results), 0)

    def testRedir1(self):
        self._setupTree2()
        outpath = path_join(self._tmpd, 'redirtest.txt')
        f= open(outpath, 'w')
        testdata = 'hello world\nhow are you?\n'
        f.write(testdata)
        f.close()
        p = Pipeline.parse("sys cat < redirtest.txt > same_redirtest.txt", self._context)
        p.execute_sync()
        newoutpath = path_join(self._tmpd, 'same_redirtest.txt')
        self.assertEquals(os.access(newoutpath, os.R_OK), True)
        same_testdata = open(newoutpath).read()
        self.assertEquals(same_testdata, testdata)
        
    def testCatBinCat(self):
        self._setupTree1()
        p = Pipeline.parse("/bin/cat testf | sys wc -l", self._context)
        p.execute_sync()
        results = list(p.get_output())
        results.sort()
        self.assertEquals(len(results), 1)
        self.assertEquals(results[0], '0\n')
        
    def testCatCatCatCat(self):
        self._setupTree1()
        p = Pipeline.parse("/bin/cat testf | /bin/cat | /bin/cat | sys wc -c", self._context)
        p.execute_sync()
        results = list(p.get_output())
        results.sort()
        self.assertEquals(len(results), 1)
        self.assertEquals(results[0], '0\n')        

    def testLs1(self):
        self._setupTree1()
        hidden = path_join(self._tmpd, '.nosee')
        open(hidden, 'w').close()
        p = Pipeline.parse("ls", self._context)
        p.execute_sync()
        results = list(p.get_output())
        self.assertEquals(len(results), 3)

    def testLs2(self):
        self._setupTree1()
        hidden = path_join(self._tmpd, '.nosee')
        open(hidden, 'w').close()
        p = Pipeline.parse("ls -a", self._context)
        p.execute_sync()
        results = list(p.get_output())
        self.assertEquals(len(results), 4)
        
    def testLs3(self):
        self._setupTree2()
        bglobpath = path_join(self._tmpd, 'testdir2', 'b*') 
        f = open(bglobpath, 'w')
        f.write('hi')
        f.close()
        p = Pipeline.parse("ls 'testdir2/b*'", self._context)
        p.execute_sync()
        results = list(p.get_output())
        self.assertEquals(len(results), 1)
        self.assertEquals(results[0].path, bglobpath)
        
