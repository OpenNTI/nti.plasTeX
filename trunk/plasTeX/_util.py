#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""


$Id$
"""

from __future__ import print_function, unicode_literals, absolute_import
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from plasTeX.DOM import Node

def subclasses(o):
	""" Return all subclasses of the given class """
	output = [o]
	for item in o.__subclasses__():
		output.extend(subclasses(item))
	return output

def sourceChildren(o, par=True):
	""" Return the LaTeX source of the child nodes """
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
	""" Return the LaTeX source of the arguments """
	return o.argSource

def ismacro(o):
	""" Is the given object a macro? """
	return hasattr(o, 'macroName')

def issection(o):
	""" Is the given object a section? """
	return o.level >= Node.DOCUMENT_LEVEL and o.level < Node.ENDSECTIONS_LEVEL

def macroName(o):
	 """ Return the macro name of the given object """
	 if o.macroName is None:
		 if type(o) is type:
			 return o.__name__
		 return type(o).__name__
	 return o.macroName
