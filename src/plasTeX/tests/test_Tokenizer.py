#!/usr/bin/env python

import unittest
from unittest import TestCase

from plasTeX.TeX import TeX
from plasTeX.Tokenizer import BeginGroup
from plasTeX.Tokenizer import EscapeSequence
from plasTeX.Tokenizer import Other
from plasTeX.Tokenizer import Space
from plasTeX.Tokenizer import Letter
from plasTeX.Tokenizer import EndGroup
from plasTeX.Tokenizer import MathShift
from plasTeX.Tokenizer import Alignment
from plasTeX.Tokenizer import Parameter
from plasTeX.Tokenizer import Superscript
from plasTeX.Tokenizer import Subscript

class TestTokenizing(TestCase):

    def testTokens(self):
        tokens = [x for x in TeX().input(r'{\hskip 36 pt}').itertokens()]
        expected = [BeginGroup('{'),
                    EscapeSequence('hskip'),
                    Other('3'),
                    Other('6'),
                    Space(' '),
                    Letter('p'),
                    Letter('t'),
                    EndGroup('}')]
        self.assertEqual(tokens, expected)

    def testComment(self):
        tokens = [x for x in TeX().input('line % comment').itertokens()]
        expected = [Letter('l'),
                    Letter('i'),
                    Letter('n'),
                    Letter('e'),
                    Space(' ')]
        self.assertEqual(tokens, expected)

    def testSymbols(self):
        tokens = [x for x in TeX().input('\\ { } $ & # ^ _ ~ %').itertokens()]
        expected = [EscapeSequence(' '),
                    BeginGroup('{'), Space(' '),
                    EndGroup('}'), Space(' '),
                    MathShift('$'), Space(' '),
                    Alignment('&'), Space(' '),
                    Parameter('#'), Space(' '),
                    Superscript('^'), Space(' '),
                    Subscript('_'), Space(' '),
                    EscapeSequence('active::~'), Space(' ')]
        self.assertEqual(tokens, expected)

        tokens = [x for x in TeX().input(r'\\ \{ \} \$ \& \# \^ \_ \~ \%').itertokens()]
        expected = [EscapeSequence('\\'), Space(' '),
                    EscapeSequence('{'), Space(' '),
                    EscapeSequence('}'), Space(' '),
                    EscapeSequence('$'), Space(' '),
                    EscapeSequence('&'), Space(' '),
                    EscapeSequence('#'), Space(' '),
                    EscapeSequence('^'), Space(' '),
                    EscapeSequence('_'), Space(' '),
                    EscapeSequence('~'), Space(' '),
                    EscapeSequence('%')]
        self.assertEqual(tokens, expected)

    def testDoubleSuper(self):
        tokens = [x for x in TeX().input('^^I ^^A ^^@ ^^M').itertokens()]
        expected = [Other('\x01'), Space(' ')]
        self.assertEqual(tokens, expected)

    def testParagraph(self):
        tokens = [x for x in TeX().input('1\n   2\n   \n   3\n').itertokens()]
        expected = [Other('1'), Space(' '),
                    Other('2'), Space(' '),
                    EscapeSequence('par'),
                    Other('3'), Space(' ')]
        self.assertEqual(tokens, expected)

    def testExercises(self):
        """ Exercises in the TeX book """
        # 8.4
        tokens = [x for x in TeX().input(r' $x^2$~  \TeX  ^^C').itertokens()]
        expected = [MathShift('$'),
                    Letter('x'),
                    Superscript('^'),
                    Other('2'),
                    MathShift('$'),
                    EscapeSequence('active::~'),
                    Space(' '),
                    EscapeSequence('TeX'),
                    Other('\x03')]
        self.assertEqual(tokens, expected)

        # 8.5
        tokens = [x for x in TeX().input('Hi!\n\n\n').itertokens()]
        expected = [Letter('H'),
                    Letter('i'),
                    Other('!'),
                    Space(' '),
                    EscapeSequence('par')]
        self.assertEqual(tokens, expected)

        # 8.6
        tokens = [x for x in TeX().input(r'^^B^^BM^^A^^B^^C^^M^^@\M ').itertokens()]
        expected = [Other('\x02'),
                    Other('\x02'),
                    Letter('M'),
                    Other('\x01'),
                    Other('\x02'),
                    Other('\x03'),
                    Space(' '),
                    EscapeSequence('M')]
        self.assertEqual(tokens, expected)

    def testParameters(self):
        tokens = [x for x in TeX().input(r'\def\foo#1[#2]{hi}').itertokens()]
        # XXX: Bad test
        self.assertTrue(tokens)

if __name__ == '__main__':
    unittest.main()
