#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""


.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

#disable: accessing protected members, too many methods
#pylint: disable=W0212,R0904

import unittest
from hamcrest import assert_that
from hamcrest import is_
from hamcrest import has_property
from hamcrest import has_entry


import tempfile

class _Persistable(object):

    def persist(self):
        return {'ref': 42}

from ..Context import Context

class TestContext(unittest.TestCase):

    def test_load_persist_stream(self):
        context = Context()
        context.persistentLabels['label'] = _Persistable()

        bytes_io = context.persist(None)

        bytes_io.seek(0) # back to beginning

        context = Context()
        context.restore(bytes_io)

        assert_that(context, has_property( 'labels',
                                           has_entry('label', has_property('ref', 42))))

    def test_load_persist_file(self):
        nf = tempfile.NamedTemporaryFile()
        try:
            context = Context()
            context.persistentLabels['label'] = _Persistable()

            context.persist(nf.name)

            context = Context()
            context.restore(nf.name)

            assert_that(context, has_property( 'labels',
                                               has_entry('label', has_property('ref', 42))))
        finally:
            nf.close()
