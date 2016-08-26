#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ZCML directives and handlers.

.. $Id$
"""

from __future__ import print_function, absolute_import, division

from zope import interface
from zope.component.zcml import utility

class IStandardTemplateEnginesDirective(interface.Interface):
    """
    Register the engines that come with this package.
    """

def registerStandardTemplateEngines(_context):
    from . import TemplateEngine
    from . import IXMLTemplateEngine
    from . import ITemplateEngine

    from . import pythontemplate
    from . import stringtemplate
    from . import htmltemplate
    from . import xmltemplate

    htmlexts = ['.html','.htm','.xhtml','.xhtm','.zpt','.pt']

    utility(_context, component=TemplateEngine(htmlexts, htmltemplate),
            provides=ITemplateEngine,
            name=u'pt')
    utility(_context, component=TemplateEngine(htmlexts, htmltemplate),
            provides=ITemplateEngine,
            name=u'zpt')
    utility(_context, component=TemplateEngine(['.xml'], xmltemplate),
            provides=IXMLTemplateEngine,
            name=u'zpt')
    utility(_context, component=TemplateEngine(htmlexts, htmltemplate),
            provides=ITemplateEngine,
            name=u'tal')
    utility(_context, component=TemplateEngine(['.xml'], xmltemplate),
            provides=IXMLTemplateEngine,
            name=u'tal')
    utility(_context, component=TemplateEngine(htmlexts, htmltemplate),
            provides=ITemplateEngine,
            name=u'html')
    utility(_context, component=TemplateEngine( ['.xml'], xmltemplate),
            provides=IXMLTemplateEngine,
            name=u'xml')

    utility(_context, component=TemplateEngine(['.pyt'], pythontemplate),
            provides=ITemplateEngine,
            name=u'python')
    utility(_context, component=TemplateEngine(['.st'], stringtemplate),
            provides=ITemplateEngine,
            name=u'string')
