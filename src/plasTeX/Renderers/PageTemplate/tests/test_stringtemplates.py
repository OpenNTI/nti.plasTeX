#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""


.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


import unittest

from .. import stringtemplate
from .. import pythontemplate

class MockObject(object):

    ownerDocument = None
    renderer = None
    parentNode = None
    config = None
    context = None

    def __init__(self):
        pass

    def __str__(self):
        return "<MockObject>"

doc = MockObject()
node = MockObject()
node.ownerDocument = doc
doc.config = {}

class TestStringTemplates(unittest.TestCase):

    def test_stringtemplate(self):
        template = b'Hi, $self.'

        call = stringtemplate(template)

        res = call(node)
        self.assertEqual(res, u'Hi, <MockObject>.')

    def test_pythontemplate(self):
        template = b'Hi, {here}.'

        call = pythontemplate(template)

        res = call(node)
        self.assertEqual(res, u'Hi, <MockObject>.')
