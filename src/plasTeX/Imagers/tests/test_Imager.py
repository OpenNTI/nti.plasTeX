#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""


$Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

#disable: accessing protected members, too many methods
#pylint: disable=W0212,R0904

import unittest

from hamcrest import assert_that
from hamcrest import is_
from hamcrest import has_length
from hamcrest.library.collection.is_empty import empty as is_empty

import os
import importlib
import glob
import tempfile

from .. import Imager
from plasTeX import TeXDocument

class TestImagers(unittest.TestCase):

    def test_file_cache(self):
        doc = TeXDocument()
        doc.config['images']['cache'] = True
        doc.userdata['working-dir'] = tempfile.gettempdir()
        imager = Imager(doc)

        with tempfile.NamedTemporaryFile() as cache_file:
            imager._filecache = cache_file.name

            imager.newImage(r'\includegraphics{foo.png}')
            assert_that( imager._cache, has_length( 1 ) )

            imager._write_cache()

            new_imager = Imager(doc)
            new_imager._filecache = cache_file.name
            new_imager._read_cache(validate_files=False)

            # Image objects in values() may not be equal
            assert_that( list(new_imager._cache.keys()), is_( list(imager._cache.keys()) ) )

            new_imager._read_cache(validate_files=True)
            assert_that( new_imager._cache, is_empty() )



def _make_check(fname):
    pname = os.path.basename(fname)
    pname = os.path.splitext(pname)[0]

    def test(self):
        self._check(pname)

    return  pname, test

class TestImports(unittest.TestCase):

    def _check(self, name):
        importlib.import_module('plasTeX.Imagers.' + name)

    for _, _fname in enumerate(sorted(glob.glob(os.path.join(os.path.dirname(__file__), '..', "*py")))):
        pname, test = _make_check(_fname)
        if pname in ('__init__', ):
            continue
        tname = 'test_' + pname
        if tname not in locals():
            locals()[tname] = test

if __name__ == '__main__':
    unittest.main()
