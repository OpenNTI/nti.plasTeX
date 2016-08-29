#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

import subprocess
import tempfile
import sys
import os

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

def _chameleon_cache():
    # A properly configured chameleon cache is the difference
    # between a 15s test run and a 2 minute test run.
    if not os.environ.get("CHAMELEON_CACHE"):
        cache_dir = os.path.join(tempfile.gettempdir(), 'plasTeXTestCache')
        try:
            os.makedirs(cache_dir)
        except OSError:
            pass
        os.environ['CHAMELEON_CACHE'] = cache_dir
        import chameleon.config as conf_mod
        if conf_mod.CACHE_DIRECTORY != cache_dir:  # previously imported before we set the environment
            conf_mod.CACHE_DIRECTORY = cache_dir
            # Which, crap, means the template is probably also screwed up.
            # It imports all of this stuff statically, and BaseTemplate
            # statically creates a default loader at import time
            import chameleon.template as temp_mod
            if temp_mod.CACHE_DIRECTORY != conf_mod.CACHE_DIRECTORY:
                temp_mod.CACHE_DIRECTORY = conf_mod.CACHE_DIRECTORY
                temp_mod.BaseTemplate.loader = temp_mod._make_module_loader()

def run_sys_executable(args=(), cwd=None):
    # Run in the current path. Must be careful to set
    # this up so it works in virtualenvs and buildout

    path = os.path.pathsep.join(sys.path)
    env = os.environ.copy()
    env['PYTHONPATH'] = path

    cmd = [sys.executable] + list(args)

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


if not os.environ.get("PLASTEX_SUBPROC"):
    # Spawning a new process is really slow under
    # PyPy, messing up all the jit work. It turns out to be much
    # faster to fork a thread and wait for it...
    # although, for some reason, it depends on the order of tests?
    # Sometimes test_longtables takes 170s, sometimes it takes just a few

    # Running inline is also a good way to make sure that we don't
    # leave things in a mess when we're done, which is important
    # because we want to be embeddable. If random tests randomly fail
    # random times using this setting, but pass if we're run in a
    # subprocess, then we're polluting global state, and the pollution
    # needs to be fixed.

    # To verify, set PLASTEX_SUBPROC=1 in the environment and try again.

    from plasTeX.plastex import main as _main

    def _run_patched(target, cmd):
        ppn = subprocess.Popen
        subprocess.Popen = lambda *args, **kwargs: None
        co = subprocess.check_output
        def check_output(cmd, **kwargs):
            if cmd[0] == 'kpsewhich':
                return cmd[1]
            return co(cmd, **kwargs)
        subprocess.check_output = check_output

        cc = subprocess.check_call
        def check_call(args, **kwargs):
            if args[0] == 'latex':
                return
            cc(args, **kwargs)
        subprocess.check_call = check_call

        try:
            target(cmd)
        finally:
            subprocess.Popen = ppn
            subprocess.check_output = co
            subprocess.check_call = cc


    def run_plastex(tmpdir, filename, args=(), cwd=None):
        _chameleon_cache()
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
        # At one time we used threads for this, for no apparent reason
        try:
            skip_if_no_binaries()
        except SkipTest:
            _run_patched(target, cmd)
        else:
            target(cmd)
else:
    import os.path

    def run_plastex(tmpdir, filename, args=(), cwd=None):
        skip_if_no_binaries()
        _chameleon_cache()
        print("WARNING: Running plastex in subprocess.")
        # Run plastex on the document
        cmd = [
            '-m', 'plasTeX.plastex',
            '-d', tmpdir
        ]
        cmd.extend(args)
        cmd.append(filename)
        return run_sys_executable(args=cmd, cwd=cwd)
