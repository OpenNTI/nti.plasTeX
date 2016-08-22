#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Various interfaces relating to plasTeX and
plugins in particular.

$Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

class IDocumentContext(interface.Interface):
    """
    An object providing the ``context`` of a
    DOM.
    """

class IPythonPackage(interface.Interface):
    """
    Implementers of this interface are representations
    of a LaTeX package (e.g., as used with \\usepackage)
    written in Python. This is typically a python module,
    though that is not required. All func:`vars` of the object
    that represent macros (having a ``macroName``) are
    loaded into the document context.

    During lookup for a package, an adapter from
    :class:`IDocumentContext` having the given name will first be
    looked for, followed by a utility with the given name; other
    search methods are considered secondary to the component lookup.
    """

    template_directory = interface.Attribute(
        """Optional attribute giving a path to a directory
    containing template files that can be used in the rendering
    of the macros implemented by this package.
    """)

    texinputs_directory = interface.Attribute(
        """Optional attribute giving a path to a directory
    containing style files (.sty) needed to make pure LaTeX
    commands happy about this package.
    """)


class IOptionAwarePythonPackage(IPythonPackage):
    """
    A python implementation of a latex package that wants to handle
    options given in its declaration.

    Although these can be registered as utilities, it is best
    to register them as adapters so that the option state is not
    forced to be global.

    The method declared on this interface will be called
    if it exists even if the object does not implement this
    interface.
    """

    def ProcessOptions( options_dict, ownerDocument ):
        """
        Process the options for the use of the package.
        """
