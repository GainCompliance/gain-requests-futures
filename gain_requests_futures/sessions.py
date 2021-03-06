# -*- coding: utf-8 -*-
"""
gain_requests_futures
~~~~~~~~~~~~~~~~

This module provides a small add-on for the requests http library. It makes use
of python 3.3's concurrent.futures or the futures backport for previous
releases of python.

    from gain_requests_futures import FuturesSession

    session = FuturesSession()
    # request is run in the background
    future = session.get('http://httpbin.org/get')
    # ... do other stuff ...
    # wait for the request to complete, if it hasn't already
    response = future.result()
    print('response status: {0}'.format(response.status_code))
    print(response.content)

"""
from concurrent.futures import Future, ThreadPoolExecutor
try:
    from concurrent.futures import ProcessPoolExecutor
except ImportError:
    pass

from functools import partial
from pickle import dumps, PickleError

from requests import Session
from requests.adapters import DEFAULT_POOLSIZE, HTTPAdapter


PICKLE_ERROR = (
    'Cannot pickle function. Refer to documentation: https://github.com/'
    'GainCompliance/gain-requests-futures/#using-processpoolexecutor'
)


class FuturesSession(Session):

    def __init__(self, executor=None, max_workers=2, session=None, *args,
                 **kwargs):
        """Creates a FuturesSession

        Notes
        ~~~~~
        * `ProcessPoolExecutor` may be used with Python > 3.4;
          see README for more information.

        * If you provide both `executor` and `max_workers`, the latter is
          ignored and provided executor is used as is.
        """
        super(FuturesSession, self).__init__(*args, **kwargs)
        self._owned_executor = executor is None
        if executor is None:
            executor = ThreadPoolExecutor(max_workers=max_workers)
            # set connection pool size equal to max_workers if needed
            if max_workers > DEFAULT_POOLSIZE:
                adapter_kwargs = dict(pool_connections=max_workers,
                                      pool_maxsize=max_workers)
                self.mount('https://', HTTPAdapter(**adapter_kwargs))
                self.mount('http://', HTTPAdapter(**adapter_kwargs))

        self.executor = executor
        self.session = session

    def prepare_request(self, request):
        if self.session:
            return self.session.prepare_request(request)
        return super(FuturesSession, self).prepare_request(request)

    def merge_environment_settings(self, *args):
        if self.session:
            return self.session.merge_environment_settings(*args)
        return super(FuturesSession, self).merge_environment_settings(*args)

    def resolve_redirects(self, resp, req, **kwargs):
        _super = super(FuturesSession, self)
        if isinstance(resp, Future):
            return _super.resolve_redirects(resp.result(), req, **kwargs)
        else:
            kwargs['_async'] = False
            return _super.resolve_redirects(resp, req, **kwargs)

    def send(self, request, _async=True, **kwargs):
        if not _async:
            return super(FuturesSession, self).send(request, **kwargs)

        if self.session:
            func = self.session.send
        else:
            func = partial(Session.send, self)

        if not isinstance(self.executor, ThreadPoolExecutor) and \
                isinstance(self.executor, ProcessPoolExecutor):
            try:
                dumps(func)
            except (TypeError, PickleError):
                raise RuntimeError(PICKLE_ERROR)

        return self.executor.submit(func, request, **kwargs)

    def close(self):
        super(FuturesSession, self).close()
        if self._owned_executor:
            self.executor.shutdown()
