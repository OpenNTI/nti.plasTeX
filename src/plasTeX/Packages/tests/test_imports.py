#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Testing that all packages can be imported.
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

#disable: accessing protected members, too many methods
#pylint: disable=W0212,R0904

import unittest

import importlib
import os.path
import glob

def _make_check(fname):
    pname = os.path.basename(fname)
    pname = os.path.splitext(pname)[0]

    def test(self):
        self._check(pname)

    return  pname, test

class TestImports(unittest.TestCase):


    def test_beamer(self):
        # Have to do this in a subprocess, it screws up
        # global state.
        from plasTeX.tests import run_sys_executable
        run_sys_executable([ '-c', 'import plasTeX.Packages.beamer'])

    def _check(self, name):
        importlib.import_module('plasTeX.Packages.' + name)

    for _, _fname in enumerate(sorted(glob.glob(os.path.join(os.path.dirname(__file__), '..', "*py")))):
        pname, test = _make_check(_fname)
        if pname in ('__init__', 'beamer'):
            # Beamer has side-effects on import, screws up the
            # argument parsing for common things. test_Crossref
            # fails if it's imported first :(
            continue
        tname = 'test_' + pname
        if tname not in locals():
            locals()[tname] = test


if __name__ == '__main__':
    unittest.main()
