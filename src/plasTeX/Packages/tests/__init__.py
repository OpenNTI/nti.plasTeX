#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""


.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from unittest import SkipTest
import subprocess
import platform
py_impl = getattr(platform, 'python_implementation', lambda: None)
IS_PYPY = py_impl() == 'PyPy'


def _skip_if_no_binaries():
    """
    If the TeX binaries are not available on the PATH in the simple
    way we use them in these tests, raise unittest's SkipTest
    exception. This supports testing on Travis CI.

    This is only a partial check and may be slow.
    """

    try:
        subprocess.check_call( ['kpsewhich', '--version'])
    except OSError:
        raise SkipTest("kpsewhich binary not found")


if not IS_PYPY:
    import os
    import os.path
    import sys
    def _run_plastex(tmpdir, filename):
        _skip_if_no_binaries()
        # Run plastex on the document
        # Must be careful to get the right python path so we work
        # in tox virtualenvs as well as buildouts
        path = os.path.pathsep.join( sys.path )
        env = dict(os.environ)
        env['PYTHONPATH'] = path
        cmd = [sys.executable,
               '-m', 'plasTeX.plastex',
               '-d', tmpdir,
               filename]
        __traceback_info__ = env, cmd
        log = subprocess.Popen( cmd,
                                env=env,
                                bufsize=-1,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT ).communicate()[0]
        __traceback_info__ = env, cmd, log
        return log
else:
    # spawning a new process is really slow under
    # pypy, messing up all the jit work. It turns out to be much
    # faster to fork a thread and wait for it...
    # although, for some reason, it depends on the order of tests?
    # Sometimes test_longtables takes 170s, sometimes it takes just a few
    # This assumes we have good separation.
    from plasTeX.plastex import main as _main
    import threading
    def _run_plastex(tmpdir, filename):
        _skip_if_no_binaries()
        cmd = ['plastex', '-d', tmpdir, filename]
        thread = threading.Thread(target=_main,
                                  args=(cmd,))
        thread.start()
        thread.join()
