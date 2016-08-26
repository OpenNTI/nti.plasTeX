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

import logging
log = logging.getLogger(__name__)
logger = log

from six.moves import configparser as ConfigParser
try:
    unicode
except NameError: # py3
    unicode = str

# Support for Python string templates
def stringtemplate(s, encoding='utf8',filename=None):
    if isinstance(s, bytes):
        s = unicode(s, encoding)
    template = string.Template(s)
    def renderstring(obj):
        tvars = {'here':obj, 'self':obj, 'container':obj.parentNode,
                 'config':obj.ownerDocument.config, 'template':template,
                 'templates':obj.renderer, 'context':obj.ownerDocument.context}
        return unicode(template.substitute(tvars))
    return renderstring

# Support for Python string formatting using the fancy
# format syntax, which is much more capable than the old '%'
# based version (for example, it can handle attribute access)
def pythontemplate(s, encoding='utf8',filename=None):
    template = s
    def renderpython(obj):
        tvars = {'here':obj, 'self':obj, 'container':obj.parentNode,
                 'config':obj.ownerDocument.config, 'template':template,
                 'templates':obj.renderer, 'context':obj.ownerDocument.context}
        return unicode(template, encoding).format(**tvars)
    return renderpython

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
        return rdr if isinstance(rdr,unicode) else unicode(rdr,encoding)
    return render
htmltemplate = zpttemplate
xmltemplate = zpttemplate

# Support for Cheetah templates
try:

    from Cheetah.Template import Template as CheetahTemplate
    from Cheetah.Filters import Filter as CheetahFilter
    class CheetahUnicode(CheetahFilter):
        def filter(self, val, encoding='utf-8', **kw):
            return unicode(val).encode(encoding)
    def cheetahtemplate(s, encoding='utf8',filename=None):
        def rendercheetah(obj, s=s):
            tvars = {'here':obj, 'container':obj.parentNode,
                     'config':obj.ownerDocument.config,
                     'context':obj.ownerDocument.context,
                     'templates':obj.renderer}
            return CheetahTemplate(source=s, searchList=[tvars],
                                   filter=CheetahUnicode).respond()
        return rendercheetah

except ImportError:

    def cheetahtemplate(s, encoding='utf8',filename=None):
        def rendercheetah(obj):
            return unicode(s, encoding)
        return rendercheetah

# Support for Kid templates
try:

    from kid import Template as KidTemplate

    def kidtemplate(s, encoding='utf8',filename=None):
        # Add namespace py: in
        s = '<div xmlns:py="http://purl.org/kid/ns#" py:strip="True">%s</div>' % s
        def renderkid(obj, s=s):
            tvars = {'here':obj, 'container':obj.parentNode,
                     'config':obj.ownerDocument.config,
                     'context':obj.ownerDocument.context,
                     'templates':obj.renderer}
            return unicode(KidTemplate(source=s,
                   **tvars).serialize(encoding=encoding, fragment=1), encoding)
        return renderkid

except ImportError:

    def kidtemplate(s, encoding='utf8',filename=None):
        def renderkid(obj):
            return unicode(s, encoding)
        return renderkid

# Support for Genshi templates
try:

    from genshi.template import MarkupTemplate as GenshiTemplate
    from genshi.template import TextTemplate as GenshiTextTemplate
    from genshi.core import Markup

    def markup(obj):
        return Markup(unicode(obj))

    def genshixmltemplate(s, encoding='utf8',filename=None):
        # Add namespace py: in
        s = '<div xmlns:py="http://genshi.edgewall.org/" py:strip="True">%s</div>' % s
        template = GenshiTemplate(s)
        def rendergenshixml(obj):
            tvars = {'here':obj, 'container':obj.parentNode, 'markup':markup,
                     'config':obj.ownerDocument.config, 'template':template,
                     'context':obj.ownerDocument.context,
                     'templates':obj.renderer}
            return unicode(template.generate(**tvars).render(method='xml',
                           encoding=encoding), encoding)
        return rendergenshixml

    def genshihtmltemplate(s, encoding='utf8',filename=None):
        # Add namespace py: in
        s = '<div xmlns:py="http://genshi.edgewall.org/" py:strip="True">%s</div>' % s
        template = GenshiTemplate(s)
        def rendergenshihtml(obj):
            tvars = {'here':obj, 'container':obj.parentNode, 'markup':markup,
                     'config':obj.ownerDocument.config, 'template':template,
                     'context':obj.ownerDocument.context,
                     'templates':obj.renderer}
            return unicode(template.generate(**tvars).render(method='html',
                           encoding=encoding), encoding)
        return rendergenshihtml

    def genshitexttemplate(s, encoding='utf8',filename=None):
        template = GenshiTextTemplate(s)
        def rendergenshitext(obj):
            tvars = {'here':obj, 'container':obj.parentNode, 'markup':markup,
                     'config':obj.ownerDocument.config, 'template':template,
                     'context':obj.ownerDocument.context,
                     'templates':obj.renderer}
            return unicode(template.generate(**tvars).render(method='text',
                           encoding=encoding), encoding)
        return rendergenshitext

except ImportError:

    def genshixmltemplate(s, encoding='utf8',filename=None):
        def rendergenshixml(obj):
            return unicode(s, encoding)
        return rendergenshixml

    def genshihtmltemplate(s, encoding='utf8',filename=None):
        def rendergenshihtml(obj):
            return unicode(s, encoding)
        return rendergenshihtml

    def genshitexttemplate(s, encoding='utf8',filename=None):
        def rendergenshitext(obj):
            return unicode(s, encoding)
        return rendergenshitext


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

    outputType = unicode
    fileExtension = '.xml'
    encodingErrors = 'xmlcharrefreplace'

    def __init__(self, *args, **kwargs):
        super(PageTemplate,self).__init__( *args, **kwargs )
        self.engines = {}

        for engine_iface in (ITextTemplateEngine, IXMLTemplateEngine, IHTMLTemplateEngine, ITemplateEngine):
            engine_type = engine_iface.getTaggedValue('engine_type')
            for name, engine in component.getUtilitiesFor(engine_iface):
                self.engines[(name, engine_type)] = engine


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
        # Create a list for resolving aliases
        self.aliases = {}

        enames = {}
        for key, value in list(self.engines.items()):
            for extension in value.extensions:
                enames[extension+'s'] = key[0]

        singleenames = {}
        for key, value in list(self.engines.items()):
            for extension in value.extensions:
                singleenames[extension] = key[0]

        if templatedir and os.path.isdir(templatedir):
            files = os.listdir(templatedir)
            # (JAM) Ensure sorted so overrides are dependable
            # (On OS X, directory listings are always sorted, thats
            # why this hasn't been a problem before)
            files.sort()

            # Compile multi-pt files first
            for f in files:
                ext = os.path.splitext(f)[-1]
                f = os.path.join(templatedir, f)

                if not os.path.isfile(f):
                    continue

                # Multi-pt files
                if ext.lower() in enames:
                    logger.debug( 'Parsing multi-pt file %s', f )
                    self.parseTemplates(f, {'engine': enames[ext.lower()]})

            # Now compile macros in individual files.  These have
            # a higher precedence than macros found in multi-pt files.
            for f in files:
                basename, ext = os.path.splitext(f)
                f = os.path.join(templatedir, f)

                if not os.path.isfile(f):
                    continue

                options = {'name':basename}

                for value in list(self.engines.values()):
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

        try:
            img = self.imager.images.get(filename, self.vectorImager.images.get(filename, self.imager.staticimages.get(filename)))
            if img is not None and getattr(img, parameter) is not None:
                if units:
                    return getattr(getattr(img, parameter), units)
                return str(getattr(img, parameter))
        except KeyError: pass

        return '&%s-%s;' % (filename, parameter)


# Set Renderer variable so that plastex will know how to load it
Renderer = PageTemplate
