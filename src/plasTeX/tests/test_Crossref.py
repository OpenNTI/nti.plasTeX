#!/usr/bin/env python

from __future__ import absolute_import, division, unicode_literals

import unittest
from unittest import TestCase
from plasTeX.TeX import TeX

from hamcrest import assert_that
from hamcrest import has_property
from hamcrest import is_not

class TestLabels(TestCase):

	def testLabel(self):
		s = TeX()
		s.input(r'\section{hi\label{one}} text \section{bye\label{two}}')
		output = s.parse()
		one = output[0]
		two = output[-1]

		__traceback_info__ = one.__dict__
		assert_that( one, has_property( 'id', 'one' ) )
		__traceback_info__ = two.__dict__
		assert_that( two, has_property( 'id', 'two' ) )


	def testLabelStar(self):
		s = TeX()
		s.input(r'\section{hi} text \section*{bye\label{two}}')
		output = s.parse()
		one = output[0]
		two = output[-1]

		__traceback_info__ = one.__dict__
		assert_that( one, has_property( 'id', 'two' ) )
		__traceback_info__ = two.__dict__
		assert_that( two, has_property( 'id', is_not( 'two' ) ) )



if __name__ == '__main__':
	unittest.main()
