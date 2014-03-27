#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""


.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"


from hamcrest import assert_that
from hamcrest import is_

import unittest, re
from unittest import TestCase
from plasTeX.TeX import TeX


def normalize(s):
	return re.sub(r'\s+', r' ', s).strip()

#pylint: disable=I0011,R0904

class TestSource(TestCase):

	def testList(self):
		tex_input = r'\begin{enumerate} \item one \item two \item three \end{enumerate}'
		s = TeX()
		s.input(tex_input)
		output = s.parse()
		source = normalize(output.source)
		assert_that( source, is_(tex_input))

		tex_input = r'\item one'
		item = output[0].firstChild
		source = normalize(item.source)
		assert_that( source, is_(tex_input))


	def testMath(self):
		tex_input = r'a $ x^{y_3} $ b'
		s = TeX()
		s.input(tex_input)
		output = s.parse()
		source = normalize(output.source)
		assert_that( source, is_(tex_input))

	def testEquation(self):
		tex_input = r'\sqrt{\pi ^{3}}'
		s = TeX()
		s.input(tex_input)

		output = s.parse()
		source = normalize(output.source)
		assert_that( source, is_(tex_input))


	def testDisplayMath(self):
		tex_input = r'a \[ x^{y_3} \]b'
		s = TeX()
		s.input(tex_input)
		output = s.parse()
		source = normalize(output.source)
		assert_that( source, is_(tex_input))


		# \begin{displaymath} ... \end{displaymath} is transformed
		# into \[ ...\]
		tex_input2 = r'a \begin{displaymath} x^{y_3} \end{displaymath}b'
		s = TeX()
		s.input(tex_input2)
		output = s.parse()
		source = normalize(output.source)
		assert_that( source, is_(tex_input))


	def testSection(self):
		tex_input = r'\section{Heading 1} foo one \subsection{Heading 2} bar two'
		s = TeX()
		s.input(tex_input)
		output = s.parse()
		source = normalize(output.source)
		assert_that( source, is_(tex_input))


		tex_input = r'\subsection{Heading 2} bar two'
		item = output[0].lastChild
		source = normalize(item.source)


	def testTabular(self):
		tex_input = r'\begin{tabular}{lll} \hline a & b & c \\[0.4in] 1 & 2 & 3 \end{tabular}'
		s = TeX()
		s.input(tex_input)
		output = s.parse()
		source = normalize(output.source)
		assert_that( source, is_(tex_input))




if __name__ == '__main__':
	unittest.main()
