#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
PageTemplate rendering interfaces.

.. $Id$
"""

from __future__ import print_function, absolute_import, division

from zope import interface
from zope.interface import taggedValue

class ITemplateEngine(interface.Interface):
    extensions = interface.Attribute("A list of file extensions")

    def compile(template, encoding="utf-8", filename=None):
        """
        Compile the template.

        Returns a callable object that takes an object and returns the
        unicode string result of rendering it.

        :param template: A string representing the template. If it
          is a byte string, it should be decoded according to *encoding*.
        :keyword str filename: If not-None, the path to the file the template
          was loaded from. This can help engines generate better error messages.
        """
    taggedValue("engine_type", None)

class IHTMLTemplateEngine(ITemplateEngine):
    taggedValue("engine_type", "html")

class IXMLTemplateEngine(ITemplateEngine):
    taggedValue("engine_type", "xml")

class ITextTemplateEngine(ITemplateEngine):
    taggedValue("engine_type", "text")
