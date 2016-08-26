#!/usr/bin/env python

import re
import codecs
from plasTeX.Renderers.PageTemplate import Renderer as _Renderer


class XHTML(_Renderer):
    """ Renderer for XHTML documents """

    fileExtension = '.html'
    imageTypes = ['.png','.jpg','.jpeg','.gif']
    vectorImageTypes = ['.svg']

    def cleanup(self, document, files, postProcess=None):
        res = _Renderer.cleanup(self, document, files, postProcess=postProcess)

        # TODO: Convert this to named registered utilities or adapters
        self.doEclipseHelpFiles(document)
        return res

    def processFileContent(self, document, s):
        s = _Renderer.processFileContent(self, document, s)

        # Force XHTML syntax on empty tags
        s = re.compile(r'(<(?:hr|br|img|link|meta|col)\b.*?)\s*/?\s*(>)',
                       re.I|re.S).sub(r'\1 /\2', s)

        # Remove empty paragraphs
        s = re.compile(r'<p>\s*</p>', re.I).sub(r'', s)

        # Add a non-breaking space to empty table cells
        s = re.compile(r'(<(td|th)\b[^>]*>)\s*(</\2>)', re.I).sub(r'\1&nbsp;\3', s)

        return s

    def doEclipseHelpFiles(self, document, encoding='ASCII'):
        """
        Generate an XML table of contents file named 'eclipse-toc.xml'.

        In the past, this was part of a set of files needed to use the
        XHTML output as Eclipse Help files, hence the method name.

        Our format, however, has diverged substantially from that
        and that's typically no longer possible.
        """

        latexdoc = document.getElementsByTagName('document')[0]

        # Create table of contents
        if 'eclipse-toc' in self:
            toc = self['eclipse-toc'](latexdoc)
            toc = re.sub(r'(<topic\b[^>]*[^/])\s*>\s*</topic>', r'\1 />', toc)
            toc = '\n'.join( [line for line in toc.split('\n') if line.strip()] ) # trim blank lines
            with codecs.open('eclipse-toc.xml', 'w', encoding, errors='xmlcharrefreplace') as f:
                f.write("<?xml version='1.0' encoding='%s' ?>\n" % encoding)
                f.write(toc)

Renderer = XHTML
