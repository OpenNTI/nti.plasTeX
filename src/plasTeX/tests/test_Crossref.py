#!/usr/bin/env python

from __future__ import absolute_import, division, unicode_literals

from unittest import TestCase
from plasTeX.TeX import TeX

from hamcrest import assert_that
from hamcrest import has_property
from hamcrest import is_not
from hamcrest import has_length


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
		assert_that( output, has_length(2) )
		section = output[0]
		section_star = output[1]

		__traceback_info__ = (section, section.__dict__, section_star, section_star.__dict__)

		assert_that( section, has_property( 'source', '\\section{hi} text \n\n'))
		assert_that( section, has_property( 'id', 'two' ) )

		assert_that( section_star, has_property( 'source', '\\section*{bye\\label{two}}'))
		assert_that( section_star, has_property( 'id', is_not( 'two' ) ) )
