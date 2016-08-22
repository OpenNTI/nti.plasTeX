from __future__ import absolute_import
#!/usr/bin/env python

from .book import *

class titleref(Command):
    args = 'label:idref'

class tightlist(Command):
    def invoke(self, tex):
        return []
        
class firmlist(Command):
    def invoke(self, tex):
        return []
