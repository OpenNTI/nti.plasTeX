#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Adapters and utilities used for traversing objects used during the
content rendering process.
"""
from __future__ import print_function, unicode_literals

import zope.traversing.adapters
from zope.location.interfaces import LocationError

class PlastexTraverser(zope.traversing.adapters.DefaultTraversable):
	"""
	Missing attributes simply return None. Many existing templates
	rely on this (instead of specifying a default fallback) since
	the plastex simpletal engine had this behaviour.

	This MUST be registered as an adapter for the DOM objects
	used in rendering.

	"""
	def traverse( self, name, furtherPath ):
		try:
			return super(PlastexTraverser,self).traverse( name, furtherPath )
		except (LocationError,IndexError):
			# IndexError can be raised because the plasTeX objects attempt
			# to use strings as child numbers
			return None
