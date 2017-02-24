#!/usr/bin/env python

"""
Generic Page Template Renderer

This module contains a plasTeX renderer that uses various types of page
templates as the templating engine.  It also makes it possible to add
support for your own templating engines.

"""
from __future__ import print_function

import sys
import os
import re
import shutil
import string

from zope import component
from zope import interface

from plasTeX.Renderers import Renderer as BaseRenderer

from .interfaces import ITextTemplateEngine
from .interfaces import IXMLTemplateEngine
from .interfaces import IHTMLTemplateEngine
from .interfaces import ITemplateEngine

from plasTeX.Logging import getLogger
log = getLogger(__name__)
logger = log

from six.moves import configparser as ConfigParser
from six import text_type

# Support for Python string templates
def stringtemplate(s, encoding='utf8',filename=None):
    if isinstance(s, bytes):
        s = s.decode(encoding)
    template = string.Template(s)
    def renderstring(obj):
        tvars = {
            'here':obj,
            'self':obj,
            'container':obj.parentNode,
            'config':obj.ownerDocument.config,
            'template':template,
            'templates':obj.renderer,
            'context':obj.ownerDocument.context
        }
        # Given a unicode argument, automatically returns a unicode
        # result.
        return template.substitute(tvars)
    return renderstring

# Support for Python string formatting using the fancy
# format syntax, which is much more capable than the old '%'
# based version (for example, it can handle attribute access)
def pythontemplate(s, encoding='utf8',filename=None):
    if isinstance(s, bytes):
        s = s.decode(encoding)
    template = s
    def renderpython(obj):
        tvars = {
            'here':obj,
            'self':obj,
            'container':obj.parentNode,
            'config':obj.ownerDocument.config,
            'template':template,
            'templates':obj.renderer,
            'context':obj.ownerDocument.context
        }
        return template.format(**tvars)
    return renderpython


def copytree(src, dest, symlink=None):
    """
    This is the same as shutil.copytree, but doesn't error out if the
    directories already exist.

    """
    for root, dirs, files in os.walk(src, True):
        if root.startswith( '.' ) or '/.' in root:
            #JAM Ignore .svn dirs
            continue

        for d in dirs:
            if d.startswith('.'):
                continue
            srcpath = os.path.join(root, d)
            destpath = os.path.join(dest, root, d)
            if symlink and os.path.islink(srcpath):
                if os.path.exists(destpath):
                    os.remove(destpath)
                os.symlink(os.readlink(srcpath), destpath)
            elif not os.path.isdir(destpath):
                os.makedirs(destpath)
                try:
                    shutil.copymode(srcpath, destpath)
                except: pass
                try:
                    shutil.copystat(srcpath, destpath)
                except: pass
        for f in files:
            if f.startswith('.'):
                continue
            srcpath = os.path.join(root, f)
            destpath = os.path.join(dest, root, f)
            if symlink and os.path.islink(srcpath):
                if os.path.exists(destpath):
                    os.remove(destpath)
                os.symlink(os.readlink(srcpath), destpath)
            else:
                shutil.copy2(srcpath, destpath)


@interface.implementer(ITemplateEngine)
class TemplateEngine(object):
    def __init__(self,  extensions, function):
        if not isinstance(extensions, (list,tuple)):
            extensions = [extensions]
        self.extensions = extensions
        self.function = function

    def compile(self, *args, **kwargs):
        return self.function(*args, **kwargs)

class PageTemplate(BaseRenderer):
    """ Renderer for page template based documents """

    outputType = text_type
    fileExtension = '.xml'
    encodingErrors = 'xmlcharrefreplace'

    def __init__(self, *args, **kwargs):
        super(PageTemplate,self).__init__( *args, **kwargs )
        self.engines = {}
        for engine_iface in (ITextTemplateEngine, IXMLTemplateEngine, IHTMLTemplateEngine, ITemplateEngine):
            engine_type = engine_iface.getTaggedValue('engine_type')
            for name, engine in component.getUtilitiesFor(engine_iface):
                self.engines[(name, engine_type)] = engine
        if not self.engines: # pragma: no cover
            logger.warning("No configured template engines found.")

    def textDefault(self, node):
        """
        Default renderer for text nodes

        This method makes sure that special characters are converted to
        entities.

        Arguments:
        node -- the Text node to process

        """
        if not(getattr(node, 'isMarkup', None)):
            node = node.replace('&', '&amp;')
            node = node.replace('<', '&lt;')
            node = node.replace('>', '&gt;')
        return self.outputType(node)

    def loadTemplates(self, document):
        """ Load and compile page templates """
        themename = document.config['general']['theme']

        # Load templates from renderer directory and parent
        # renderer directories
        sup = list( type(self).__mro__ )
        sup.reverse()

        theme_search_paths = []
        seen = set()
        def _import( path, kind='', extra='' ):
            path = os.path.abspath( path )
            if path in seen:
                return
            seen.add( path )
            log.info('Importing %s templates from %s (%s)', kind, path, extra )
            self.importDirectory( path )
            # Store theme location
            theme_search_paths.append( os.path.join( path, 'Themes' ) )


        for cls in sup:
            if cls is BaseRenderer or cls is object or cls is dict:
                continue
            # FIXME: Note that this doesn't work with zipped modules
            cwd = os.path.dirname(sys.modules[cls.__module__].__file__)
            _import( cwd, kind='class', extra=cls )

            # Load templates configured by the environment variable
            templates = os.environ.get('%sTEMPLATES' % cls.__name__,'')
            for path in [x.strip() for x in templates.split(os.pathsep) if x.strip()]:
                _import( path, kind='envrn')

        for path in [x.strip() for x in document.userdata.get('package_template_paths', '').split(os.pathsep) if x.strip()]:
            _import( path, kind='packg' )

        def _find_theme( name ):
            if not name: return None
            for theme_search_path in reversed( theme_search_paths ):
                theme_dir = os.path.join( theme_search_path, name )
                if os.path.isdir( theme_dir ):
                    return theme_dir
            return None

        def _copy_theme(dest, extensions_to_ignore):
            # Assumes we are in the theme directory
            for item in os.listdir('.'):
                if os.path.isdir(item):
                    if not os.path.isdir(os.path.join(dest,item)):
                        os.makedirs(os.path.join(dest,item))
                    copytree(item, dest, True)
                elif os.path.splitext(item)[-1].lower() not in extensions_to_ignore:
                    shutil.copy(item, os.path.join(dest,item))

        def _get_base_theme( theme_dir ):
            p = ConfigParser.SafeConfigParser()
            p.read( os.path.join( theme_dir, 'theme_conf.ini' ) )
            for conf in (p,document.config):
                if conf.has_option( 'general', 'theme-base' ):
                    return conf.get( 'general', 'theme-base' )

        def _import_and_copy_theme_with_bases( themename ):
            theme_dir = _find_theme( themename )
            if theme_dir and os.path.isdir( theme_dir ):
                base_theme_name = _get_base_theme( theme_dir )
                _import_and_copy_theme_with_bases( base_theme_name )

                log.info('Importing theme templates from %s', theme_dir)
                self.importDirectory(theme_dir)


                if document.config['general']['copy-theme-extras']:
                    extensions = ['.ini'] # Don't copy the theme_conf.ini file
                    for e in list(self.engines.values()):
                        extensions += e.extensions + [x + 's' for x in e.extensions]

                    # Copy all theme extras
                    cwd = os.getcwd()
                    os.chdir(theme_dir)
                    _copy_theme(cwd, extensions)
                    os.chdir(cwd)

        _import_and_copy_theme_with_bases( themename )


    def render(self, document, postProcess=None):
        """ Load templates and render the document """
        self.loadTemplates(document)
        super(PageTemplate,self).render(document, postProcess=postProcess)

    def importDirectory(self, templatedir):
        """
        Compile all ZPT files in the given directory

        Templates can exist in two different forms.  First, a template
        can be a file unto itself.  If an XML template is desired,
        the file should have an extension of .xml, .xhtml, or .xhtm.
        If an HTML template is desired, the files should have an
        extension of .zpt, .html, or .htm.  You can also configure
        your own page templates with their own extensions.

        If you have many small templates, or a template that corresponds
        to more than one macro, you can use a multiple ZPT file.  A
        multiple ZPT file contains directives within it to delimit
        individual page templates as well as specify which macros they
        correspond to and what type of template they are (i.e. XML or
        HTML).

        MZPT files are loaded first, followed by standalone templates. Files are
        loaded in alphabetic order in order to give a dependable override order, since
        later templates of the same name will override earlier templates of the
        same name. (JAM)

        Required Arguments:
        templatedir -- the directory to search for template files

        """
        # Create a list for resolving aliases; always clear these at the beginning
        self.aliases = {}
        if not templatedir or not os.path.isdir(templatedir):
            logger.debug("Not a directory: %s", templatedir)
            return

        enames = {}
        for key, value in self.engines.items():
            for extension in value.extensions:
                enames[extension + 's'] = key[0]

        singleenames = {}
        for key, value in self.engines.items():
            for extension in value.extensions:
                singleenames[extension] = key[0]


        files = os.listdir(templatedir)
        # (JAM) Ensure sorted so overrides are dependable
        # (On OS X, directory listings are always sorted, thats
        # why this hasn't been a problem before)
        files.sort()
        files = [os.path.join(templatedir, f) for f in files]
        files = [f for f in files if os.path.isfile(f)]

        logger.debug("Possible template files in %s: %s",
                     files, templatedir)

        # Compile multi-pt files first
        for f in files:
            ext = os.path.splitext(f)[-1]

            # Multi-pt files
            if ext.lower() in enames:
                logger.debug( 'Parsing multi-pt file %s', f )
                self.parseTemplates(f, {'engine': enames[ext.lower()]})

        # Now compile macros in individual files.  These have
        # a higher precedence than macros found in multi-pt files.
        for f in files:
            basename, ext = os.path.splitext(f)
            basename = os.path.basename(basename)
            options = {'name': basename}

            for value in self.engines.values():
                if ext in value.extensions:
                    options['engine'] = singleenames[ext.lower()]
                    self.parseTemplates(f, options)
                    del options['engine']
                    break

        if self.aliases:
           log.warning('The following aliases were unresolved: %s',
                        ', '.join(list(self.aliases.keys())))

    def setTemplate(self, template, options, filename=None):
        """
        Compile template and set it in the renderer

        Required Arguments:
        template -- the content of the template to be compiled
        options -- dictionary containing the name (or names) and type
            of the template

        :return: The template compiled by the engine. (JAM)

        """

        # Get name
        try:
            names = options['name'].split()
            if not names:
                names = [' ']
        except KeyError:
            raise ValueError( 'No name given for template' )

        # If an alias was specified, link the names to the
        # already specified template.
        if 'alias' in options:
            alias = options['alias'].strip()
            for name in names:
                self.aliases[name] = alias
            if ''.join(template).strip():
                log.warning('Both an alias and a template were specified for: %s', ', '.join(names))

        # Resolve remaining aliases
        for key, value in list(self.aliases.items()):
            if value in self:
                self[key] = self[value]
            self.aliases.pop(key)

        if 'alias' in options:
            return

        # Compile template and add it to the renderer
        template = ''.join(template).strip()
        ttype = options.get('type')
        if ttype is not None:
            ttype = ttype.lower()
        engine = options.get('engine','zpt').lower()

        templateeng = self.engines.get((engine, ttype),
                                       self.engines.get((engine, None)))

        try:
            template = templateeng.compile(template,filename=filename)
        except Exception as e:
            raise ValueError( 'Could not compile template "%s" %s' % (names[0], e) )

        for name in names:
            logger.debug1("Storing template %s = %r (%s)", name, template, filename)
            self[name] = template

        return template

    def parseTemplates(self, filename, options=None):
        """
        Parse templates from the file and set them in the renderer

        Required Arguments:
        filename -- file to parse templates from

        Keyword Arguments:
        options -- dictionary containing initial parameters for templates
            in the file

        """
        template = []
        options = options.copy() if options is not None else {}
        defaults = options.copy()
        name = None
        logger.debug("Parsing templates from %s (%r)", filename, options)
        if not options or 'name' not in options:
            f = open(filename, 'r')
            for i, line in enumerate(f):

                #JAM: Enable python-like line comments in zpt files (ZPT has other comment types)
                #FIXME If other template engines rely on '#'
                #this breaks badly
                if line.startswith('#'):
                    continue

                # Found a meta-data command
                if re.match(r'(default-)?\w+:', line):

                    # parse any awaiting templates
                    if template:
                        try:
                            self.setTemplate('\n'.join(template).rstrip(), # Preserve line breaks
                                             options,
                                             filename=filename)
                        except ValueError:
                            logger.exception( "Failed to parse template at line %s in %s", i, filename )

                        options = defaults.copy()
                        template = []

                    # Done purging previous template, start a new one
                    name, value = line.split(':', 1)
                    name = name.strip()
                    value = value.rstrip()
                    while value.endswith('\\'):
                        value = value[:-1] + ' '
                        for line in f:
                            value += line.rstrip()
                            break

                    value = re.sub(r'\s+', r' ', value.strip())
                    if name.startswith('default-'):
                        name = name.split('-')[-1]
                        defaults[name] = value
                        if name not in options:
                            options[name] = value
                    else:
                        options[name] = value
                    continue

                if template or (not(template) and line.strip()):
                    template.append(line)
                elif not(template) and 'name' in options:
                    template.append('')
            f.close()
        else:
            with open(filename, 'r') as f:
                template = f.readlines()

        # Purge any awaiting templates
        if template:
            try:
                self.setTemplate(''.join(template), options, filename=filename)
            except ValueError as msg:
                print('ERROR: %s in template %s in file %s' % (msg, ''.join(template), filename))

        elif name and not template:
            self.setTemplate('', options, filename=filename)

    def processFileContent(self, document, s):
        # Add width, height, and depth to images
        s = re.sub(r'&amp;(\S+)-(width|height|depth);(?:&amp;([a-z]+);)?',
                   self.setImageData, s)

        # Convert characters >127 to entities
        # XXX: FIXME: This is broken for non-BMP Unicode
        # characters in Python 2 narrow builds, because they
        # come back as two characters (a surrogate pair)
        if document.config['files']['escape-high-chars']:
            s = list(s)
            for i, item in enumerate(s):
                if ord(item) > 127:
                    s[i] = '&#%.3d;' % ord(item)
            s = u''.join(s)

        return super(PageTemplate,self).processFileContent(document, s)

    def setImageData(self, m):
        """
        Substitute in width, height, and depth parameters in image tags

        The width, height, and depth parameters aren't known until after
        all of the output has been generated.  We have to post-process
        the files to insert this information.  This method replaces
        the &filename-width;, &filename-height;, and &filename-depth;
        placeholders with their appropriate values.

        Required Arguments:
        m -- regular expression match object that contains the filename
            and the parameter: width, height, or depth.

        Returns:
        replacement for entity

        """
        filename, parameter, units = m.group(1), m.group(2), m.group(3)
        print('SID', m, filename, parameter, units)
        try:
            img = self.imager.images.get(filename,
                                         self.vectorImager.images.get(filename,
                                                                      self.imager.staticimages.get(filename)))
            print(img, type(getattr(img, parameter)))
            if img is not None and getattr(img, parameter) is not None:
                if units:
                    return getattr(getattr(img, parameter), units)
                return str(getattr(img, parameter))
        except KeyError:
            import traceback; traceback.print_exc()
            pass
        print("Nothing found")
        return '&%s-%s;' % (filename, parameter)


# Set Renderer variable so that plastex will know how to load it
Renderer = PageTemplate
