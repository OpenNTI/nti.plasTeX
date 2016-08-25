#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""


.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from plasTeX.tests import run_plastex

def _run_plastex(outdir, filename, *args):
    # Export old name with old signature
    return run_plastex(outdir, filename, args=args)

from bs4 import BeautifulSoup as _Soup

def BeautifulSoup(markup, parser=None):
    if parser is None:
        parser = "html.parser"
    return _Soup(markup, parser)
