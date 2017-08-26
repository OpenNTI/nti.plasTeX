#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import sys

PY3 = sys.version_info[0] == 3
PY2 = sys.version_info[0] == 2
PY26 = sys.version_info[0:2] == (2, 6)
PY27 = sys.version_info[0:2] == (2, 7)
PYPY = hasattr(sys, 'pypy_translation_info')

from plasTeX.DOM import Node

from six import unichr as chr
chr_ = chr  # pylint

if PY3:  # pragma: no cover
    def _unicode(s): return str(s)
else:
    _unicode = unicode


def text_(s, encoding='utf-8', err='strict'):
    """
    Decode a byte sequence and unicode result
    """
    s = s.decode(encoding, err) if isinstance(s, bytes) else s
    return _unicode(s) if s is not None else None


def subclasses(o):
    """ 
    Return all subclasses of the given class
    """
    output = [o]
    for item in o.__subclasses__():
        output.extend(subclasses(item))
    return output


def sourceChildren(o, par=True):
    """ 
    Return the LaTeX source of the child nodes
    """
    if o.hasChildNodes():
        if par:
            return u''.join([x.source for x in o.childNodes])
        else:
            source = []
            for par in o.childNodes:
                source += [x.source for x in par]
            return u''.join(source)
    return u''


def sourceArguments(o):
    """ 
    Return the LaTeX source of the arguments 
    """
    return o.argSource


def ismacro(o):
    """ 
    Is the given object a macro? 
    """
    return hasattr(o, 'macroName')


def issection(o):
    """ 
    Is the given object a section? 
    """
    return o.level >= Node.DOCUMENT_LEVEL and o.level < Node.ENDSECTIONS_LEVEL


def macroName(o):
    """ 
    Return the macro name of the given object 
    """
    if o.macroName is None:
        if type(o) is type:
            return o.__name__
        return type(o).__name__
    return o.macroName
