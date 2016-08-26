#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Support for ZPT rendering.

.. note:: Importing this module monkey-patches chameleon
   to accept 'self' as a path argument alias for 'here'.

.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

# Support for ZPT HTML and XML templates was originally provided via
# an embedded copy of simpleTAL. This version instead uses Chameleon
# and some other parts of the Zope/Repoze ecosystem.

# The simpletal implementation did have some conveniences, such as
# use of 'self' and some more lax traversing rules. These are replicated
# here.

from z3c.pt.pagetemplate import PageTemplate as Z3CPageTemplate
from chameleon.zpt.template import PageTemplate as ChameleonPageTemplate
from chameleon.zpt.program import MacroProgram as BaseMacroProgram
from chameleon.astutil import Builtin

import ast

class MacroProgram(BaseMacroProgram):
    """For compatibility with simpletal, we default everything to be non-escaped (substitition)"""
    def _make_content_node( self, expression, default, key, translate ):
        return BaseMacroProgram._make_content_node( self, expression, default, 'substitution', translate )

class _NTIPageTemplate(Z3CPageTemplate):
    def parse(self, body):
        if self.literal_false:
            default_marker = ast.Str(s="__default__")
        else:
            default_marker = Builtin("False")
        # For compatibility with simpletal, we default everything to be non-escaped (substitition)
        program = MacroProgram(
            body, self.mode, self.filename,
            escape=False,
            default_marker=default_marker,
            boolean_attributes=self.boolean_attributes,
            implicit_i18n_translate=self.implicit_i18n_translate,
            implicit_i18n_attributes=self.implicit_i18n_attributes,
            trim_attribute_space=self.trim_attribute_space,
            )
        return program

# Allow all of the chameleon expression types, like import...
_NTIPageTemplate.expression_types = ChameleonPageTemplate.expression_types.copy()
# ...except where they are overridded explicitly
_NTIPageTemplate.expression_types.update(Z3CPageTemplate.expression_types)
_NTIPageTemplate.expression_types['stripped'] = _NTIPageTemplate.expression_types['path']

# NOTE: Depending on import order, this may or may not disable access
# to z3c.macro, which only places itself in the BaseTemplate types,
# expecting to be inherited

import chameleon.utils
import chameleon.template
class _Scope(chameleon.utils.Scope):
    """The existing simpletal templates assume 'self', which is not valid
    in TAL because the arguments are passed as kword args, and 'self' is already
    used. Thus, we use 'here' and then override."""
    def __getitem__( self, key ):
        if key == 'self':
            key = 'here'
        return chameleon.utils.Scope.__getitem__( self, key )
chameleon.template.Scope = _Scope

def zpttemplate(s, encoding='utf8', filename=None):
    # It improves error message slightly if we keep the body around
    # The source is not as necessary, but what the heck, it's only memory
    config = {'keep_body': True, 'keep_source': True}
    if filename:
        config['filename'] = filename
    template = _NTIPageTemplate( s, **config )

    def render(obj):
        context = {
            'here': obj,
            'container': obj.parentNode,
            'config': obj.ownerDocument.config,
            'context': obj.ownerDocument.context,
            'template': template,
            'templates': obj.renderer
        }
        rdr = template.render( **context )
        if isinstance(rdr, bytes):
            rdr = rdr.decode(encoding)
        return rdr
    return render
