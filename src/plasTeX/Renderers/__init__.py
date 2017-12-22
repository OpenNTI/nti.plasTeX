#!/usr/bin/env python
from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

import os
import six
import codecs
from six.moves import urllib_parse

from zope.dottedname.resolve import resolve as resolve_import

from plasTeX.Filenames import Filenames
from plasTeX.DOM import Node, Document
from plasTeX.Logging import getLogger
#from plasTeX.Imagers import Image, PILImage
from plasTeX.Imagers import Imager as DefaultImager, VectorImager as DefaultVectorImager

log = getLogger(__name__)
status = getLogger(__name__ + '.status')

from six import string_types
try:
    unicode
except NameError:
    unicode = str # py3

__all__ = ['Renderer','Renderable']

def baseclasses(cls):
    return [x for x in cls.mro() if x is not object]
    # What's the difference between this and mro()?
    #  mro() is only defined on new-style classes;
    #  this could result in multiple copies of the same class
    #output = [cls]
    #for item in cls.__bases__:
    #   output.extend(baseclasses(item))
    #return [x for x in output if x is not object]

def mixin(base, mix, overwrite=False):
    """
    Mix the methods and members of class `mix` into `base`

    Required Arguments:
    base -- the base class to add mixin to
    mix -- the mixin class

    """
    if '_mixed_' not in vars(base):
        base._mixed_ = {}
    mixed = base._mixed_
    for cls in baseclasses(mix):
        for item, value in list(vars(cls).items()):
            if item in ['__dict__','__module__','__doc__','__weakref__']:
                continue
            if overwrite or item not in vars(base):
                old = vars(base).get(item, None)
                setattr(base, item, value)
                mixed[item] = (mix, old)

def unmix(base, mix=None):
    """
    Remove mixed in methods and members

    Required Arguments:
    base -- the base class to remove mixins from

    Keyword Arguments:
    mix -- the mixin class to remove from `base`

    """
    # pylint: disable=protected-access
    if mix is None:
        for key, value in list(base._mixed_.items()):
            if value[1] is not None:
                setattr(base, key, value[1])
            else:
                delattr(base, key)
        del base._mixed_
    else:
        for key, value in list(base._mixed_.items()):
            if value[0] is mix:
                if value[1] is not None:
                    setattr(base, key, value[1])
                else:
                    delattr(base, key)
        if not base._mixed_:
            del base._mixed_

def _as_unicode(child, val):
    # If a plain string is returned, we have no idea what
    # the encoding is, but we'll make a guess.

    if type(val) is unicode or isinstance(val, unicode):
        return val

    log.warning('The renderer for %s returned a non-unicode string.  Using the default input encoding.',
                type(child).__name__)
    val = unicode(val, child.config['files']['input-encoding'])
    return val

def render_children(r, childNodes):
    """
    :return: An iterable of Unicode objects representing the rendered
        versions of `childNodes`. Note that the lengths may not be equal
        if children were written to files.
    """
    # Render all child nodes
    s = []
    for child in childNodes:

        # Short circuit text nodes
        if child.nodeType == Node.TEXT_NODE:
            s.append(r.textDefault(child))
            continue

        # Short circuit macros that have unicode equivalents
        uni = child.unicode
        if uni is not None:
            s.append(r.textDefault(uni))
            continue

        layouts, names = [], []
        nodeName = child.nodeName
        modifier = None

        # Does the macro have a modifier (i.e. '*')
        if child.attributes:
            modifier = child.attributes.get('*modifier*')

        if child.filename:

            # Force footnotes to be cached
            getattr( child, 'footnotes', None )

            status.info('Rendering %s', child.filename)

            # Filename and modifier
            if modifier:
                layouts.append('%s-layout%s' % (nodeName, modifier))

            # Filename only
            layouts.append('%s-layout' % nodeName)

        # Modifier only
        if modifier:
            names.append('%s%s' % (nodeName, modifier))

        names.append(nodeName)
        layouts.append('default-layout')

        # Locate the rendering callable, and call it with the
        # current object (i.e. `child`) as its argument.
        func = r.find(names, r.default)
        val = func(child)
        val = _as_unicode( child, val )

        # If the content should go to a file, write it and go
        # to the next child.
        if child.filename:
            filename = child.filename

            # Create any directories as needed
            directory = os.path.dirname(filename)
            if directory and not os.path.isdir(directory):
                os.makedirs(directory)

            # Add the layout wrapper if there is one
            func = r.find(layouts)
            if func is not None:
                val = func(StaticNode(child, val))
                val = _as_unicode( child, val )


            # Write the file content
            with codecs.open(filename, 'w',
                             child.config['files']['output-encoding'],
                             errors=r.encodingErrors) as f:
                f.write(val)

            continue


        # Append the resultant unicode object to the output
        s.append(val)

    return s

_render_children = render_children

def renderable_as_unicode( self ):
    """
    Invoke the rendering process on all of the child nodes.

    """
    r = self.renderer

    # Short circuit macros that have unicode equivalents
    uni = self.unicode
    if uni is not None:
        return r.outputType(r.textDefault(uni))

    # If we don't have childNodes, then we're done
    if not self.hasChildNodes():
        return ''

    # At the very top level, only render the DOCUMENT_LEVEL node
    if self.nodeType == Node.DOCUMENT_NODE:
        childNodes = (x for x in self.childNodes
                      if x.level == Node.DOCUMENT_LEVEL)
    else:
        childNodes = self.childNodes

    # Render all child nodes
    s = _render_children( r, childNodes )

    return r.outputType(''.join(s))

class RenderableMixin(object):
    """
    Base class for all renderable nodes

    This class is mixed into nodes of the document object prior to
    rendering.  The actual rendering method is __unicode__.

    """

    def __unicode__(self):
        """
        Invoke the rendering process on all of the child nodes.

        Uses :func:`renderable_as_unicode` to allow subclasses to be able
        to duplicate this method (because it's not possible to call
        :func:`super` in a mixed-in subclass).

        """
        return renderable_as_unicode( self )

    def __str__(self):
        v = self.__unicode__()
        if v is None:
            return str('')
        return v

    @property
    def image(self):
        """ Generate an image and return the image filename """
        return self.renderer.imager.getImage(self)

    @property
    def vectorImage(self):
        """ Generate a vector image and return the image filename """
        image = self.renderer.vectorImager.getImage(self)
        image.bitmap = self.renderer.imager.getImage(self)
        return image

    @property
    def url(self):
        """
        Return the relative URL of the object

        If the object actually creates a file, just the filename will
        be returned (e.g. foo.html).  If the object is within a file,
        both the filename and the anchor will be returned
        (e.g. foo.html#bar).

        """
        override = getattr(self, 'urloverride', None)
        if override is not None:
            return override

        base = self.config['document']['base-url']
        if base and base.endswith('/'):
            base = base[:-1]

        # If this generates a file, return that filename
        if self.filename:
            if base:
                return URL('%s/%s' % (base, self.filename))
            return URL(self.filename)

        # If this is a location within a file, return that location
        node = self.parentNode
        while node is not None and node.filename is None:
            node = node.parentNode
        filename = ''
        if node is not None:
            filename = node.filename

        if base:
            return URL('%s/%s#%s' % (base, filename, self.url_fragment))
        return URL('%s#%s' % (filename, self.url_fragment))

    @property
    def url_fragment(self):
        """
        The ``id`` of this node, suitable for use in a url fragment.
        """
        return urllib_parse.quote(self.id.encode('utf-8'))

    @property
    def html_id(self):
        """
        The ``id`` of this node, suitable for use in an HTML ``id``
        attribute.

        From the spec: \"The value must be unique amongst all the IDs
        in the element's home subtree and must contain at least one
        character. The value must not contain any space characters.

        There are no other restrictions on what form an ID can take; in
        particular, IDs can consist of just digits, start with a digit, start
        with an underscore, consist of just punctuation, etc.
        \"

        Therefore, we do not need to URL escape this, simply replace spaces.
        """
        return self.id.replace(' ', '%20')

    @property
    def filename(self):
        """
        The filename that this object should create

        Objects that don't create new files should simply return `None`.

        """
        r = self.renderer
        try:
            return r.files[self]
        except KeyError:
            pass

        filename = None
        override = None
        try:
            # Nothing in the plasTeX code base actually ever
            # sets a filenameoverride on a Node
            override = str(self.filenameoverride.encode('ascii','ignore')) if self.filenameoverride is not None else None
            if override:
                assert override is not None
                userdata = self.ownerDocument.userdata
                config = self.ownerDocument.config
                newFilename = Filenames(override,
                                        (config['files']['bad-chars'],
                                         config['files']['bad-chars-sub']),
                                         {'jobname': userdata.get('jobname','')},
                                        r.fileExtension)
                newFilename.forceExtension = True
                filename = r.files[self] = newFilename()

        except (AttributeError, ValueError) as e:
            if isinstance( e, ValueError ):
                log.exception( "Failed to generate filename given override %s", override )

            if not hasattr(self, 'config'):
                return

            level = getattr(self, 'splitlevel', self.config['files']['split-level'])

            # If our level doesn't invoke a split, don't return a filename
            if self.level > level:
                return

            # Populate vars of filename generator
            # and call the generator to get the filename.
            # FIXME: Eww, not thread safe. Not really even re-entrant.
            # Closely coupled to the implementation of `id`
            ns = r.newFilename.vars
            if hasattr(self, 'id') and getattr(self, '@hasgenid', None) is None:
                ns['id'] = self.id
            if hasattr(self, 'title'):
                if hasattr(self.title, 'textContent'):
                    ns['title'] = self.title.textContent
                elif isinstance(self.title, string_types):
                    ns['title'] = self.title

            r.files[self] = filename = r.newFilename()

        return filename

Renderable = RenderableMixin # BWC

def _create_imager(config, document, defaultImager, imageTypes, imageUnits, imageAttrs, kind='imager'):
    imager = None
    # Instantiate appropriate imager
    names = [x for x in config['images'][kind].split() if x]
    for name in names:
        if name == 'none':
            break

        Imager = None
        try:
            # Custom takes priority
            Imager = resolve_import( "%s.Imager" % name )
        except ImportError:
            log.exception( "Could not load custom imager %s", name )
            try:
                Imager = resolve_import( "plasTeX.Imagers.%s.Imager" % name )
            except ImportError:
                log.exception( "Could not load default imager %s", name )
        if Imager is None:
            continue

        imager = Imager(document, imageTypes)

        # Make sure that this imager works on this machine
        if imager.verify():
            log.info('Using the imager "%s".', name)
            break

        imager = None

    # Still no imager? Just use the default.
    if imager is None:
        if 'none' not in names:
            log.warning('Could not find a valid %s in the list: %s. The default %s will be used.', kind, names, kind)

        imager = defaultImager(document, imageTypes)

    if imageTypes and imager.fileExtension not in imageTypes:
        imager.fileExtension = imageTypes[0]
    if imageAttrs and not imager.imageAttrs:
        imager.imageAttrs = imageAttrs
    if imageUnits and not imager.imageUnits:
        imager.imageUnits = imageUnits

    return imager

# JAM: Make access to the current renderer thread-safe.
# In the usual case, when rendering a document, we'll make
# sure to set the renderer on the document object.
# On PyPy, we MUST use a proper identifier
Node.renderer = property(lambda self: getattr( self, '__renderer', getattr( self.ownerDocument, 'renderer', None) ),
                         lambda self, nv: setattr( self, '__renderer', nv ) if nv is not None else delattr( self, "__renderer" ),
                         lambda self: delattr(self, '__renderer') if hasattr( self, '__renderer' ) else None    )

Document.renderer = property(lambda self: getattr( self, '__renderer', None),
                             lambda self, nv: setattr( self, '__renderer', nv ) if nv is not None else delattr( self, "__renderer" ),
                             lambda self: delattr(self, '__renderer') if hasattr( self, '__renderer' ) else None    )
class Renderer(dict):
    """
    Base class for all renderers

    All renderers must act like a dictionary.  Each macro that is encountered
    in a document must have a corresponding key in the renderer.  This
    key points to a callable object which is called with the object to
    be rendered.

    In addition to callable renderers, the renderer also handles image
    generation.  Images are generated when the output document type can
    not support the rendering of a macro.  One example of this is equations
    in HTML.

    """

    renderableClass = RenderableMixin
    renderMethod = None
    textDefault = unicode
    default = unicode
    outputType = unicode
    imageTypes = []
    vectorImageTypes = []
    fileExtension = ''
    imageAttrs = '&${filename}-${attr};'
    imageUnits = '&${units};'
    encodingErrors = 'replace'

    def __init__(self, data=None):
        if data:
            dict.__init__(self, data)
        else:
            dict.__init__(self)

        # Names of generated files
        self.files = {}

        # Instantiated at render time
        self.imager = None
        self.vectorImager = None

        # Filename generator
        self.newFilename = None

    def cacheFilenames(self, node):
        """
        Generate filenames in order

        Since filenames are generated on demand, in order to make the
        nodes have a filename that corresponds to its position in the document,
        the filenames must be generated before rendering the document.

        Required Arguments:
        node -- the top-level node in the document

        """
        # Using the side-effect of the filename property
        getattr(node, 'filename')
        for child in node.childNodes:
            self.cacheFilenames(child)

    def render(self, document, postProcess=None):
        """
        Invoke the rendering process

        This method invokes the rendering process as well as handling
        the setup and shutdown of image processing.

        Required Arguments:
        document -- the document object to render
        postProcess -- a function that will be called with the content of

        """
        config = document.config

        # If there are no keys, print a warning.
        # This is most likely a problem.
        if not bool(self):
            log.warning('There are no keys in the renderer.  ' +
                        'All objects will use the default rendering method.')

        document.renderer = self # JAM: Make thread safe. See above

        # XXX JAM FIXME: Not thread safe because this manipulates
        # the Node class system wide
        # We can get very close to being thread safe by instead
        # operating on a zope proxy object that extends self.renderableClass
        # and takes care to wrap self.childNodes, but this
        # ultimately fails because some things like SectionUtils
        # are already mixed-in to the node and depend on things defined
        # by renderableClass (filename)...thus they can only be used
        # during the rendering process anyway, but they don't get to
        # work on the proxy object. Obviously that's a design flaw
        # to rectify.
        mixin(Node, self.renderableClass)
        try:

            # Create a filename generator
            self.newFilename = Filenames(config['files'].get('filename', raw=True),
                                         (config['files']['bad-chars'],
                                          config['files']['bad-chars-sub']),
                                         {'jobname':document.userdata.get('jobname', '')},
                                         self.fileExtension)

            self.cacheFilenames(document)

            # Instantiate appropriate imager
            self.imager = _create_imager(config, document, DefaultImager, self.imageTypes, self.imageUnits, self.imageAttrs)

            # Instantiate appropriate vector imager
            self.vectorImager = _create_imager(config, document, DefaultVectorImager, self.vectorImageTypes, self.imageUnits, self.imageAttrs, kind='vector-imager')


            # Invoke the rendering process
            if self.renderMethod:
                getattr(document, self.renderMethod)()
            else:
                unicode(document)

            # Finish rendering images
            self.imager.close()
            self.vectorImager.close()

            # Run any cleanup activities
            self.cleanup(document, list(self.files.values()), postProcess=postProcess)

            # Write out auxilliary information
            pauxname = os.path.join(document.userdata.get('working-dir','.'),
                                    '%s.paux' % document.userdata.get('jobname',''))
            rname = config['general']['renderer']
            document.context.persist(pauxname, rname)
        finally:
            # Remove mixins
            unmix(Node, self.renderableClass)
            del document.renderer

    def processFileContent(self, document, s):
        return s

    def cleanup(self, document, files, postProcess=None):
        """
        Cleanup method called at the end of rendering

        This method allows you to do arbitrary post-processing after
        all files have been rendered.

        Note: While I greatly dislike post-processing, sometimes it's
              just easier...

        Required Arguments:
        document -- the document being rendered
        files -- the list of filenames that were generated

        Optional Arguments:
        postProcess -- a function that will be called on the content of
            each file.  It is called with the document object and a
            unicode object with the content of each file.
            It must return a unicode object.

        """
        if self.processFileContent is Renderer.processFileContent:
            return

        encoding = document.config['files']['output-encoding']

        for f in files:
            try:
                with codecs.open(str(f), 'r', encoding,
                                errors=self.encodingErrors) as sf:
                    s = sf.read()
            except IOError:
                log.exception("Failed to re-read file %s", f)
                continue

            orig = s
            s = self.processFileContent(document, s)

            if callable(postProcess):
                s = postProcess(document, s)

            if s != orig:
                assert isinstance(s, unicode)
                with codecs.open(f, 'w', encoding) as sf:
                    sf.write(s)

    def find(self, keys, default=None):
        """
        Locate a renderer given a list of possibilities

        Required Arguments:
        keys -- a list of strings containing the requested name of
            a renderer.  This list is traversed in order.  The first
            renderer that is found is returned.

        Keyword Arguments:
        default -- the renderer to return if none of the keys exists

        Returns:
        the requested renderer

        """
        for key in keys:
            if key in self:
                return self[key]

        # Other nodes supplied default
        log.warning('Using default renderer for %s', ', '.join(keys))
        for key in keys:
            self[key] = default
        return default



class StaticNode(object):
    """
    Object to assist in rendering files

    This object is used to wrap objects that need to have a layout
    file wrapped around them.  The layout wrapper generally includes
    all of the navigation links, table of contents, etc.

    This is simply a proxy object that returns the attributes of
    the given object.  The exceptions are __unicode__ and __str__
    which simply return the rendered string that was passed in.
    This allows you to use two templates: one that renders the content
    and another that is wrapped around any node that generates a
    file.  Without this, you can easily run into infinite recursion
    problems.

    """
    def __init__(self, obj, content):
        """
        Initialize the static node

        Arguments:
        obj -- the object that contains navigation and table of
            contents information
        content -- the rendered object in a unicode string

        """
        self._node_data = (obj, content)
    def __getattribute__(self, name):
        if name in ['_node_data','__unicode__','__str__']:
            return object.__getattribute__(self, name)
        return getattr(self._node_data[0], name)
    def __unicode__(self):
        return self._node_data[1]
    def __str__(self):
        return self.__unicode__()


class URL(unicode):

    def relativeTo(self, src):
        """
        Get the path of this URL relative to `src'

        """
        if isinstance(src, Node):
            src = src.url

        dest, src = os.path.normpath(str(self)), os.path.normpath(src)
        base = os.path.join(*(['a/'] * max(dest.count('/'), src.count('/'))))
        src = os.path.join(base, src).split('/')
        dest = os.path.join(base, dest).split('/')

        same = 0
        for d, s in zip(dest, src):
            if d == s:
                same += 1
                continue
            break

        dest, src = dest[same:], src[same:-1]

        if src:
            return type(self)(os.path.join(os.path.join(*(['..'] * len(src))),
                                           os.path.join(*dest)))

        return type(self)(os.path.join(*dest))
