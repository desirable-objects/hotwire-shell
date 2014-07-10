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

import threading, Queue, logging

from hotwire.gutil import call_timeout,remove_idle
from hotwire.externals.singletonmixin import Singleton

_logger = logging.getLogger("hotwire.Async")

class MiniThreadPool(Singleton):
    """A Thread pool.  Seems like a missing battery from the Python standard library..."""
    def __init__(self):
        _logger.debug("Creating MiniThreadPool")
        self.__queue_cond = threading.Condition()
        self.__queue = []
        self.__avail_threads = 0
        self.__thread_count = 0
        self.__max_threads = 7
        self.__async_serial = 0

    def run(self, callable, args=()):
        self.__queue_cond.acquire()
        if not self.__avail_threads and self.__thread_count < self.__max_threads:
            thr = threading.Thread(target=self.__worker, name="MiniThreadPool Thread")
            _logger.debug("Created thread %s", thr)
            thr.setDaemon(True)
            thr.start()
            self.__thread_count += 1
        serial = self.__async_serial
        self.__async_serial += 1
        self.__queue.append((serial, callable, args))
        self.__queue_cond.notify()
        self.__queue_cond.release()
        return serial
    
    def cancel(self, serial):
        # FIXME implement
        pass
            
    def __worker(self):
        while True:
            _logger.debug("thread %s waiting", threading.currentThread())
            self.__queue_cond.acquire()
            self.__avail_threads += 1
            while not self.__queue:
                self.__queue_cond.wait()
            (serial, cb, args) = self.__queue.pop(0)
            self.__avail_threads -= 1
            self.__queue_cond.release()
            try:
                _logger.debug("thread %s executing cb", threading.currentThread())
                cb(*args)
            except:
                logging.exception("Exception in thread pool worker")

class IterableQueue(Queue.Queue):
    def __init__(self):
        Queue.Queue.__init__(self)
        self.__lock = threading.Lock()
        self.__handler_idle_id = 0
        self.__handler = None
        self.__handler_args = None
        self.__timeout_kwargs = None

    def connect(self, handler, *args, **kwargs):
        self.__lock.acquire()
        assert(self.__handler is None)
        self.__handler_args = args
        self.__timeout_kwargs = kwargs
        self.__handler = handler
        self.__lock.release()
        if not self.empty():
            self.__add_idle()

    def disconnect(self):
        _logger.debug("disconnecting from queue %r", self)
        self.__lock.acquire()
        self.__handler = None
        if self.__handler_idle_id > 0:
            remove_idle(self.__handler_idle_id)
            self.__handler_idle_id = 0
        self.__lock.release()

    def __do_idle(self):
        self.__lock.acquire()
        self.__handler_idle_id = 0
        handler = self.__handler
        self.__lock.release()
        if handler:
            return handler(self, *self.__handler_args)

    def __add_idle(self):
        self.__lock.acquire()
        if self.__handler_idle_id == 0 and self.__handler:           
            self.__handler_idle_id = call_timeout(200, self.__do_idle, **self.__timeout_kwargs)
        self.__lock.release()

    def put(self, *args):
        Queue.Queue.put(self, *args)
        self.__add_idle()
        
    def iter_avail(self):
        try:
            while True:
                val = self.get(False)
                yield val
        except Queue.Empty, e:
            pass

    def __iter__(self):
        for obj in QueueIterator(self):
            yield obj

class QueueIterator(object):
    def __init__(self, source):
        self._source = source

    def __iter__(self):
        item = True
        while not (item is None):
            item = self._source.get()
            if not (item is None):
                yield item
            else:
                break
