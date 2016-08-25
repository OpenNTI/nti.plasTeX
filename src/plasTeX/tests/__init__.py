#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

import subprocess
import platform
py_impl = getattr(platform, 'python_implementation', lambda: None)
IS_PYPY = py_impl() == 'PyPy'

from unittest import SkipTest

def _real_check_for_binaries():
    with open('/dev/null', 'wb') as f: # Unix specific (prior to Python 3)
        subprocess.check_call( ['kpsewhich', '--version'], stdout=f)

_check_for_binaries = _real_check_for_binaries

def _already_checked_for_binaries_and_failed():
    raise SkipTest("kpsewhich binary not found")

def _already_checked_for_binaries_and_worked():
    return

def skip_if_no_binaries():
    """
    If the TeX binaries are not available on the PATH in the simple
    way we use them in these tests, raise unittest's SkipTest
    exception. This supports testing on Travis CI.

    This is only a partial check and may be slow.
    """
    global _check_for_binaries
    try:
        _check_for_binaries()
        _check_for_binaries = _already_checked_for_binaries_and_worked
    except OSError:
        _check_for_binaries = _already_checked_for_binaries_and_failed
        _already_checked_for_binaries_and_failed()


if not IS_PYPY:
    import os
    import os.path
    import sys

    def run_plastex(tmpdir, filename, args=(), cwd=None):
        skip_if_no_binaries()
        # Run plastex on the document
        # Must be careful to get the right python path so we work
        # in tox virtualenvs as well as buildouts
        path = os.path.pathsep.join(sys.path)
        env = os.environ.copy()
        env['PYTHONPATH'] = path
        cmd = [
            sys.executable,
            '-m', 'plasTeX.plastex',
            '-d', tmpdir
        ]
        cmd.extend(args)
        cmd.append(filename)
        __traceback_info__ = env, cmd
        proc = subprocess.Popen( cmd,
                                 env=env,
                                 cwd=cwd,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE )
        out, err = proc.communicate()
        log = out + err
        __traceback_info__ = env, cmd, log
        if proc.returncode:
            raise OSError("plastex failed with code %s:\n%s" % (proc.returncode, log))
        return log
else:
    # spawning a new process is really slow under
    # pypy, messing up all the jit work. It turns out to be much
    # faster to fork a thread and wait for it...
    # although, for some reason, it depends on the order of tests?
    # Sometimes test_longtables takes 170s, sometimes it takes just a few

    # This assumes we have good separation and don't pollute/alter global
    # modules. This used to be a very false assumption but is getting more
    # true as time goes on. Eventually this should become the default.

    from plasTeX.plastex import main as _main
    import threading
    def run_plastex(tmpdir, filename, args=(), cwd=None):
        skip_if_no_binaries()
        cmd = ['plastex', '-d', tmpdir]
        cmd.extend(args)
        cmd.append(filename)
        target = _main
        if cwd:
            def target(*args):
                pwd = os.getcwd()
                os.chdir(cwd)
                try:
                    _main(*args)
                finally:
                    os.chdir(pwd)
        thread = threading.Thread(target=target,
                                  args=(cmd,))
        thread.start()
        thread.join()
