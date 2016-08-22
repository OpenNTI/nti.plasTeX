#!/usr/bin/env python

from __future__ import absolute_import
from __future__ import division

import re
from plasTeX import Command

from .graphics import DeclareGraphicsExtensions, graphicspath, _locate_image_file

class includegraphics(Command):
    args = '* [ options:dict ] file:str'
    packageName = 'graphicx'
    captionable = True

    default_extensions = ('.png','.jpg','.jpeg','.gif','.pdf','.ps','.eps')

    def invoke(self, tex):
        res = Command.invoke(self, tex)

        f = self.attributes['file']
        img = _locate_image_file( self, tex, f, self.packageName, self.default_extensions )

        options = self.attributes['options']

        if options is not None:

            scale = options.get('scale')
            if scale is not None:
                scale = float(scale)
                from PIL import Image
                w, h = Image.open(img).size
                self.style['width'] = '%spx' % (w * scale)
                self.style['height'] = '%spx' % (h * scale)

            height = options.get('height')
            if height is not None:
                self.style['height'] = height

            width = options.get('width')
            if width is not None:
                self.style['width'] = width

            def getdimension(s):
                m = re.match(r'^([\d\.]+)\s*([a-z]*)$', s)
                if m and '.' in m.group(1):
                    return float(m.group(1)), m.group(2)
                elif m:
                    return int(m.group(1)), m.group(2)

            keepaspectratio = options.get('keepaspectratio')
            if img is not None and keepaspectratio == 'true' and \
               height is not None and width is not None:
                from PIL import Image
                w, h = Image.open(img).size

                height, hunit = getdimension(height)
                width, wunit = getdimension(width)

                scalex = float(width) / w
                scaley = float(height) / h

                if scaley > scalex:
                    height = h * scalex
                else:
                    width = w * scaley

                self.style['width'] = '%s%s' % (width, wunit)
                self.style['height'] = '%s%s' % (height, hunit)

        self.imageoverride = img

        return res

class DeclareGraphicsExtensions(DeclareGraphicsExtensions):
    packageName = 'graphicx'

class graphicspath(graphicspath):
    packageName = 'graphicx'
