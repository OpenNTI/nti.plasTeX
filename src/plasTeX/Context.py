#!/usr/bin/env python

from __future__ import print_function, absolute_import, division

import os
import re
import time
import codecs
import io

import plasTeX
from ._util import ismacro, macroName

from plasTeX.Logging import getLogger
from plasTeX.Tokenizer import Tokenizer, Token, DEFAULT_CATEGORIES, VERBATIM_CATEGORIES

import zope.dottedname.resolve
from zope import component
from zope import interface
from .interfaces import IDocumentContext
from .interfaces import IPythonPackage

from six.moves import configparser as ConfigParser
from six.moves import cPickle as pickle
from six import string_types

# Only export the Context singleton
__all__ = ['Context']

# Set up loggers
log = getLogger(__name__)
status = getLogger(__name__ + '.status')
stacklog = getLogger(__name__ + '.context.stack')
macrolog = getLogger(__name__ + '.context.macros')

class ContextItem(dict):
    """
    Localized macro/category code stack element

    """

    def __init__(self, data=None):
        dict.__init__(self, data or {})
        self.categories = None
        self.obj = None
        self.parent = None
        self.owner = None

    @property
    def name(self):
        if self.obj is not None:
            return self.obj.nodeName
        return '{}'

    def __getitem__(self, key):
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            if self.parent is not None and self.parent is not self:
                return self.parent[key]
            raise

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def has_key(self, key):
        if dict.__contains__(self, key):
            return True
        if self.parent is not None:
            return key in self.parent

    __contains__ = has_key

    def keys(self):
        keys = {}
        for key in dict.keys(self):
            keys[key] = 0
        if self.parent is not None:
            for key in list(self.parent.keys()):
                keys[key] = 0
        return list(keys.keys())

    def __str__(self):
        if self.parent is not None:
             return '%s -> %s' % (self.parent, self.name)
        return str(self.name)


class Counters(dict):
    def __getitem__(self, name):
        try:
            c = dict.__getitem__(self, name)
        except KeyError:
#           log.warning('No counter "%s" exists.  Creating one.' % name)
            c = self[name] = plasTeX.Counter(self.context, name)
        return c


class LanguageParser(object):
    """ Parser for language commands """

    def __init__(self, output=None):
        self.data = output if output is not None else {}
        self.language = None
        self.term = None

    def parse(self, files, encoding='UTF-8'):
        from xml.parsers import expat
        if isinstance(files, string_types):
            files = [files]
        for file in files:
            if not os.path.isfile(file):
                continue
            self.parser = expat.ParserCreate('UTF-8')
            self.parser.StartElementHandler = self.startElement
            self.parser.EndElementHandler = self.endElement
            self.parser.CharacterDataHandler = self.charData
            with codecs.open(file, 'r', encoding) as f:
                self.parser.Parse(f.read().encode('UTF-8'))
        self.mergeLanguages()
        return self.data

    def mergeLanguages(self):
        # Merge language keys from the major language section, into
        # the minor language section
        for key, value in list(self.data.items()):
            if '-' in key:
                major, minor = key.split('-',1)
                if major in self.data:
                    majordict = self.data[major]
                    for mkey, mvalue in list(majordict.items()):
                        if mkey not in value:
                            value[mkey] = mvalue

    def startElement(self, name, attrs):
        if name == 'terms':
            self.term = None
            if self.data.get(attrs['lang']):
                self.language = self.data[attrs['lang']]
            else:
                self.language = self.data[attrs['lang']] = {}
            if 'babel' in attrs:
                self.data[attrs['babel']] = self.language
        elif name == 'term':
            self.term = attrs['name']
            self.language[self.term] = u''

    def endElement(self, name):
        if name == 'term':
            self.term = None

    def charData(self, data):
        if self.term:
            self.language[self.term] += data

# FIXME: JAM: Most uses of "str(name)" to create
# named counters should probably become "unicode(name)"?
# As it is, our unicode objects are being copied into bytestrings
# Of course, this changes under Py3

@interface.implementer(IDocumentContext)
class Context(object):
    """
    Object to handle macro contexts within a TeX document

    This class keeps track of macros (both global and local), labels,
    context groupings, category codes, etc.  The TeX parser uses this
    class to hold any and all information about the document currently
    being processed.  This class also contains methods to generate
    new counters, ifs, dimensions, and other commands and macros.

    """

    def globals(self):
        return self.contexts[0]

    def __init__(self, load=False):
        # Stack of ContextItems
        self.contexts = []

        # Object that the current label points to
        self.currentlabel = None

        # Labeled objects
        self.labels = {}
        self.persistentLabels = {}

        # Unresolved refs
        self.refs = {}

        # LaTeX counters
        self.counters = Counters()
        self.counters.context = self

        # Tokens aliased by \let
        self.lets = {}

        # Imported packages and their options
        self.packages = {}

        # Output files
        self.writes = {}

        # Depth of the context stack
        self.depth = 0

        # Holds the current environment name stack
        self._currenvir = []

        # Holds the terms for various languages
        self.languages = {}
        self.terms = {}
        self.currentLanguage = ''

        # Create a global namespace
        self.push()

        self.warnOnUnrecognized = True

        if load:
            self.loadBaseMacros()

    def currenvir():
        def fget(self):
            if self._currenvir:
                return self._currenvir[-1]
            return
        def fset(self, value):
            if value is None:
                self._currenvir.pop()
            else:
                self._currenvir.append(value)
        def fdel(self):
            self._currenvir.pop()
        return locals()
    currenvir = property(**currenvir())

    def persist(self, filename_or_stream, rtype='none'):
        """
        Persist cross-document information for labeled nodes

        :param filename_or_stream: Either a path to a file,
            or an instance of :class:`io.IOBase` in bytes mode.
            If you pass None, we will persist to an in-memory
            byte stream and return that stream. If you pass an
            open stream, we do not close it.

        :keyword rtype: The key in the shelved data to look under.
            This is generally the name of the renderer used since the information for each
            renderer may be different.
        """
        needs_close = False
        if isinstance(filename_or_stream, string_types):
            try:
                # If it exists, open it as-is
                stream = io.open(filename_or_stream, 'r+b')
            except IOError:
                # If we cannot open it (doesn't exist usually)
                # try to create it.
                # NOTE: there is a race condition here
                stream = io.open(filename_or_stream, 'w+b')
            needs_close = True
        elif filename_or_stream is None:
            stream = io.BytesIO()
        else:
            stream = filename_or_stream

        # Read from the stream the pickled data; if we just
        # created an empty file, we must be prepared for EOF
        # XXX: JAM: In the past, this used to ignore
        # all Exceptions and remove a file if it existed.
        # That's probably not right?
        try:
            try:
                d = pickle.load(stream)
            except EOFError:
                d = {}

            if rtype not in d:
                d[rtype] = {}

            data = d[rtype]
            for key, value in list(self.persistentLabels.items()):
                data[key] = value.persist()

            # Great, we read the values. Seek to the beginning
            # and truncate the file, then write back, because
            # we may have added auxilliary info
            stream.seek(0)
            stream.truncate()

            pickle.dump(d, stream, pickle.HIGHEST_PROTOCOL)
        finally:
            if needs_close:
                stream.close()
        return stream

    def restore(self, filename_or_stream, rtype='none'):
        """
        Restore cross-document information for labeled nodes

        :param filename_or_stream: Either the path to an
            file, or an open readably bytes instance
            of :class:`io.IOBase`. If you pass an open
            stream, we do not close it.
        :keyword rtype: The key in the shelved data to look under.
            This is generally the name of the renderer used since the information for each
            renderer may be different.

        """
        stream = None
        needs_close = False

        if filename_or_stream is None:
            return

        if isinstance(filename_or_stream, string_types):
            if not os.path.exists(filename_or_stream):
                return
            stream = io.open(filename_or_stream, 'rb')
            needs_close = True
        else:
            stream = filename_or_stream

        wou = self.warnOnUnrecognized
        try:
            d = pickle.load(stream)
            data = d.get(rtype, {})


            self.warnOnUnrecognized = False
            for key, value in list(data.items()):
                n = self[value.get('macroName','Macro')]()
                n.restore(value)
                self.labels[key] = n

        finally:
            self.warnOnUnrecognized = wou
            if needs_close:
                stream.close()

    @property
    def isMathMode(self):
        """ Are we in math mode or not? """
        for i in range(len(self.contexts)-1, -1, -1):
            obj = self.contexts[i].obj
            if obj is not None and obj.mathMode is not None:
                return obj.mathMode
        return False

    def loadBaseMacros(self):
        """ Import all builtin macros """
        from plasTeX import Base # TODO: Circular imports
        self.importMacros(vars(Base))

    def loadLanguage(self, lang, document):
        """
        Load a localized version of macros for a particular language

        Required Arguments:
        lang -- the name of the language file to load

        """
        if not self.languages:
            files = document.config['document']['lang-terms'].split(os.pathsep)
            files.append(os.path.join(os.path.dirname(__file__), 'i18n.xml'))
            LanguageParser(self.languages).parse(reversed(files))

        if lang in self.languages:
            self.currentLanguage = lang
            self.newcommand('languagename', definition=lang)
            self.terms = self.languages[lang]
            for key, value in list(self.languages[lang].items()):
                if key == 'today':
                    self.newcommand(key, definition=self._strftime(value))
                else:
                    self.newcommand('%sname' % key, definition=value)
        else:
            log.warning('Could not load language "%s", american will be used instead' % lang)

    def _strftime(self, fmt):
        if '%f' in fmt or '%e' in fmt:
            day = time.strftime('%d')
            suffix = 'th'
            if day.endswith('1'):
                suffix = 'st'
            elif day.endswith('2'):
                suffix = 'nd'
            elif day.endswith('3'):
                suffix = 'rd'
            day = str(int(day))
            return time.strftime(fmt.replace('%f', day+suffix).replace('%e', day))
        return time.strftime(fmt)

    def loadINIPackage(self, inifile):
        """
        Load INI file containing macro definitions

        Arguments:
        inifile -- filename of INI formatted file

        """
        ini = ConfigParser.RawConfigParser()
        if not isinstance(inifile, (list,tuple)):
            inifile = [inifile]
        for f in inifile:
            ini.read(f)
            macros = {}
            for section in ini.sections():
                try: baseclass = self[section]
                except KeyError:
                    log.warning('Could not find macro %s', section)
                    continue
                for name in ini.options(section):
                    value = ini.get(section,name)
                    m = re.match(r'^unicode\(\s*(?:(\'|\")(?P<string>.+)(?:\1)|(?P<number>\d+))\s*\)$',value)
                    if m:
                        data = m.groupdict()
                        if data['number'] is not None:
                            value = unichr(int(data['number']))
                        else:
                            value = unicode(data['string'])
                        macros[name] = type(name, (baseclass,),
                                            {'unicode': value})
                        continue
                    macros[name] = type(name, (baseclass,),
                                        {'args': value})
            self.importMacros(macros)

    def loadPackage(self, tex, package_file, options=None):
        """
        Load a Python or LaTeX package

        A Python version of the package is searched for first,
        if one cannot be found then a LaTeX version of the package
        is searched for.

        Required Arguments:
        tex -- the instance of the TeX engine to use for parsing
            the LaTeX file, if needed.
        file -- the name of the file to load

        Keyword Arguments:
        options -- the options given on the macro to pass to the package

        Returns:
        boolean indicating whether or not the package loaded successfully

        """
        module_name = os.path.splitext(package_file)[0]

        # See if it has already been loaded
        if module_name in self.packages:
            return True

        needs_legacy_ini_file = False
        global_packagesini = os.path.join(os.path.dirname(plasTeX.Packages.__file__),
                                          os.path.basename(module_name) + '.ini')

        # First, can we find an adapter?
        package = component.queryAdapter( self, IPythonPackage, name=module_name )
        # Otherwise, is there a utility?
        if package is None:
            package = component.queryUtility( IPythonPackage, name=module_name )
        # Finally, the fallback lookup based off of sys.path
        if package is None:
            needs_legacy_ini_file = True
            try:
                # Try to import a Python package by that name
                #m = __import__(module, globals(), locals())
                # JAM: We want to allow for dottednames
                try:
                    package = zope.dottedname.resolve.resolve( module_name )
                except (ValueError,SystemError):
                    # JAM: plastex tries to put its raw Packages directory
                    # on sys.path. This is broken as soon as any of those packages
                    # try to import each other in an absolute fashion, as is required
                    # in python 3. You get "'Attempted relative import in non-package'" in
                    # Py2 as a ValueError, and in py3 you get " Parent module '' not loaded, cannot perform relative import"
                    # as a SystemError
                    if '.' not in module_name:
                        package = zope.dottedname.resolve.resolve( 'plasTeX.Packages.' + module_name )
            except ImportError as e:
                # No Python module
                if 'No module' in str(e):
                    #pass
                    # Failed to load Python package
                    log.debug('No Python version of %s was found', package_file, exc_info=True)
                # Error while importing
                else:
                    raise

        if package is not None:
            status.debug('Loaded package %s (%s)', package_file, getattr( package, '.__file__', package) )
            if hasattr(package, 'ProcessOptions'):
                package.ProcessOptions(options or {}, tex.ownerDocument)
            self.importMacros(vars(package))
            if needs_legacy_ini_file:
                moduleini = os.path.splitext(package.__file__)[0] + '.ini'
                self.loadINIPackage([global_packagesini, moduleini])

            # Now extend the list of template paths if necessary
            # See Renderers.PageTemplate
            if getattr(package, 'template_directory', None):
                document = tex.ownerDocument
                paths = document.userdata.get('package_template_paths', '').split(os.pathsep)
                paths.append( package.template_directory )
                document.userdata['package_template_paths'] = os.pathsep.join( paths )

            # And likewise for TEXINPUTS. Note that we do not
            # change the current environment, these are for passing to
            # subprocesses we control
            if getattr(package, 'texinputs_directory', None):
                document = tex.ownerDocument
                paths = document.userdata.get('texinputs_paths', '').split(os.pathsep)
                paths.append( package.texinputs_directory )
                document.userdata['texinputs_paths'] = os.pathsep.join( paths )

            self.packages[module_name] = options

            return True



        result = tex.loadPackage(package_file, options)
        try:
            moduleini = os.path.join(os.path.dirname(tex.kpsewhich(package_file)),
                                     os.path.basename(module_name) + '.ini')
            self.loadINIPackage([global_packagesini, moduleini])
        except OSError:
            pass
        return result


    def label(self, label, node=None):
        """
        Set a label to the current labelable object

        Required Arguments:
        label -- string that contains the label

        Keyword Arguments:
        node -- a node to apply the label to rather than the currently
            labelable object

        See Also:
        self.ref()

        """
        label = label.strip()
        if not label:
            return

        if node is None:
            node = self.currentlabel

        if node is not None:
            self.persistentLabels[label] = self.labels[label] = node
            node.id = label

        #print( "Labeling %s with '%s' refs %s" % (self.currentlabel, label, self.currentlabel.ref) )

        # Resolve any outstanding references to this object
        if label in self.refs and label in self.labels:
            for obj in self.refs[label]:
                for key, value in list(obj.idref.items()):
                    if value.id != label:
                        continue
                    obj.idref[key] = self.labels[label]
            del self.refs[label]

    def ref(self, obj, name, label):
        """
        Set up a ref for resolution

        Required Arguments:
        obj -- object to put the referenced object onto
        name -- name of key in idref dictionary where object is stored
        label -- label to resolve

        See Also:
        self.label()

        """
        label = label.strip()
        if not label:
            return

        # Resolve ref if label already exists
        if label in self.labels:
            obj.idref[name] = self.labels[label]
            return

        # If the label doesn't exist, store away the object for later
        if label not in self.refs:
            self.refs[label] = []
        self.refs[label].append(obj)

        # Make a fake node with the ID on it for now
        node = self['Macro']()
        node.id = label
        obj.idref[name] = node

    def __getitem__(self, key):
        """
        Look through the stack of macros and return the requested one

        Required Arguments:
        key -- name of macro

        Returns: instance of requested macro

        """
        try:
            return self.top[key]
        except KeyError:
            pass

        # Didn't find it, so generate a new class
        if self.warnOnUnrecognized and not self.isMathMode:
            log.warning('unrecognized command/environment: %s', key)

        self[key] = newclass = type(str(key), (plasTeX.UnrecognizedMacro,), {})
        return newclass

    def push(self, context=None):
        """
        Add a new context to the stack

        This adds a new context grouping to the stack.  A context
        grouping includes both a set of localized macros and localized
        category codes.

        Keyword Arguments:
        context -- macro instance to use as the basis for a context
            grouping.  The local macros and category codes of this
            instance are used.  If this argument isn't supplied,
            an empty context is created.

        """
        if not self.contexts:
            context = ContextItem()
            context.categories = DEFAULT_CATEGORIES[:]
            self.contexts.append(context)

        else:
            name = '{}'
            if context is not None:
                name = context.nodeName
                # If we hit a document element, make sure that we start
                # at the global context.
                if context.level == context.DOCUMENT_LEVEL:
                    stacklog.debug1( "Popping all contexts up to document due to %r", context )

                    while len(self.contexts) > 1:
                        self.contexts.pop()
            stacklog.debug1('pushing %s onto %s', name, self.top)
            self.contexts.append(self.createContext(context))

        self.mapMethods()

    append = push

    # JAM: XXX: It's not legitimate to be defining __contains__
    # as an instance attribute in a new-style class, we must
    # delegate it directly
    def __contains__(self, key):
        return key in self.top

    def mapMethods(self):
        # Getter methods use the most local context
        self.top = top = self.contexts[-1]
        self.__getitem__ = top.__getitem__
        self.__contains__ = top.__contains__
        self.get = top.get
        self.keys = top.keys
        self.has_key = top.has_key
        self.categories = top.categories

        # Setter methods always use the global namespace
        self.update = top.update
        self.__setitem__ = self.contexts[0].__setitem__

        # Set up inheritance attributes
        self.top.owner = self
        if len(self.contexts) > 1:
            self.top.parent = self.contexts[-2]

        self.depth = len(self.contexts)

    def createContext(self, obj=None):
        """
        Create the pieces of a new context (i.e. macros and category codes)

        Keyword Arguments:
        obj -- macro instance to use as the basis for a context
            grouping.  The local macros and category codes of this
            instance are used.  If this argument isn't supplied,
            an empty context is created.

        Returns: ContextItem instance

        """
        newcontext = ContextItem()
        newcontext.categories = self.categories
        newcontext.obj = obj

        if obj is not None:

            # Get the local category codes and macros
#           if obj.categories is not None:
#               newcontext.categories = obj.categories

            newcontext.update(obj.locals())

        return newcontext

    def importMacros(self, context):
        """
        Import macros from given context into the global namespace

        Required Arguments:
        context -- dictionary of macros to import

        """
        for value in list(context.values()):
            if ismacro(value):
                self[macroName(value)] = value
#           elif isinstance(value, Context):
#               self.importMacros(value)

    def pop(self, obj=None):
        """
        Remove a context from the stack

        Keyword Arguments:
        index -- index of context item to remove

        Returns: ContextItem instance removed from stack

        """

        #stacklog.debug1( 'Popping %s %s from %s', obj, type(obj), self.contexts[-1] )

        if obj is None:
            # Pop until we hit a None in the context
            while len(self.contexts) > 1:
                if self.contexts[-1].obj is None:
                    self.contexts.pop()
                    break
                self.contexts.pop()
        else:
            while len(self.contexts) > 1:
                o = self.contexts[-1].obj
                # If None, keep going
                if o is None:
                    pass
                # Found context pushed by ourself
                elif o is obj:
                    self.contexts.pop()
                    break
                # Don't pop parent node
                elif o is obj.parentNode:
                    break
                # Found the \begin to our \end
                elif type(obj) == type(o) and obj.macroMode == obj.MODE_END:
                    self.contexts.pop()
                    break
                # Found the \foo to our \endfoo
                elif obj.nodeName == ('end%s' % o.nodeName):
                    self.contexts.pop()
                    break
                self.contexts.pop()

        self.mapMethods()

    def addGlobal(self, key, value):
        """
        Add a macro to the global context

        Required Arguments:
        key -- name of macro to add
        value -- item to add to the global namespace.  If the item
            is a macro instance, it is simply added to the namespace.
            If it is a string, it is converted into a string Command
            instance before being added.

        """
        if isinstance(value, string_types):
            newvalue = plasTeX.Command()
            newvalue.unicode = value
            value = newvalue

        elif not ismacro(value):
            raise ValueError('"%s" does not implement the macro interface' % key)

        self.contexts[0][macroName(value)] = value

    __setitem__ = addGlobal

    def addLocal(self, key, value):
        """
        Add a macro to the local context

        Required Arguments:
        key -- name of macro to add
        value -- item to add to the global namespace.  If the item
            is a macro instance, it is simply added to the namespace.
            If it is a string, it is converted into a string Command
            instance before being added.

        """
        if isinstance(value, string_types):
            newvalue = plasTeX.Command()
            newvalue.unicode = value
            value = newvalue

        elif not ismacro(value):
            raise ValueError('"%s" does not implement the macro interface' % key)

        self.contexts[-1][macroName(value)] = value

    def whichCode(self, char):
        """
        Return the character code that `char` belongs to

        Required Arguments:
        char -- character to determine the code of

        Returns: integer category code of the given character

        """
        c = self.categories
        if char in c[Token.CC_LETTER]:
            return Token.CC_LETTER
        if char in c[Token.CC_SPACE]:
            return Token.CC_SPACE
        if char in c[Token.CC_EOL]:
            return Token.CC_EOL
        if char in c[Token.CC_BGROUP]:
            return Token.CC_BGROUP
        if char in c[Token.CC_EGROUP]:
            return Token.CC_EGROUP
        if char in c[Token.CC_ESCAPE]:
            return Token.CC_ESCAPE
        if char in c[Token.CC_SUPER]:
            return Token.CC_SUPER
        if char in c[Token.CC_SUB]:
            return Token.CC_SUB
        if char in c[Token.CC_MATHSHIFT]:
            return Token.CC_MATHSHIFT
        if char in c[Token.CC_ALIGNMENT]:
            return Token.CC_ALIGNMENT
        if char in c[Token.CC_COMMENT]:
            return Token.CC_COMMENT
        if char in c[Token.CC_ACTIVE]:
            return Token.CC_ACTIVE
        if char in c[Token.CC_PARAMETER]:
            return Token.CC_PARAMETER
        if char in c[Token.CC_IGNORED]:
            return Token.CC_IGNORED
        if char in c[Token.CC_INVALID]:
            return Token.CC_INVALID
        return Token.CC_OTHER

    def catcode(self, char, code):
        """
        Set the category code for a particular character

        Required arguments:
        char -- the character to set the code of
        code -- the category code number to set `char` to

        """
        c = self.contexts[-1].categories = self.categories = self.categories[:]
        for i in range(0,16):
            c[i] = c[i].replace(char, '')
        # Don't insert if it's code 12.
        if code != 12:
            c[code] += char

    def setVerbatimCatcodes(self):
        """
        Set the category codes up for parsing verbatims

        This method turns the category codes for all characters to CC_OTHER

        """
        self.contexts[-1].categories = self.categories = VERBATIM_CATEGORIES[:]

    def newcounter(self, name, resetby=None, initial=0, format=None):
        """
        Create a new counter

        This method corresponds to LaTeX's \\newcounter command

        Required Arguments:
        name -- name of the counter.  The generate counter class will
            use this name.  Also, a new macro called 'the<name>' will
            also be generated for the counter format.

        Keyword Arguments:
        resetby -- the name of the counter that this counter is reset by
        initial -- initial value for the counter

        """
        name = str(name)
        # Counter already exists
        if name in self.counters:
            macrolog.debug('counter %s already defined', name)

            return
        self.counters[name] = plasTeX.Counter(self, name, resetby, initial)

        if format is None:
            format = '${%s}' % name
        newclass = type('the'+name, (plasTeX.TheCounter,),
                        {'format': format})
        self.addGlobal('the' + name, newclass)

    def newwrite(self, name, file):
        """
        Create a new output file

        Required Arguments:
        name -- the key name for the file
        file -- the file name to open

        """
        self.writes[name] = open(file, 'w')

    def newcount(self, name, initial=0):
        """
        Create a new count (like \\newcount)

        Required Arguments:
        name -- name of count to create

        Keyword Arguments:
        initial -- value to initialize to

        """
        name = str(name)
        # Generate a new count class
        macrolog.debug1('creating count %s', name)
        newclass = type(name, (plasTeX.CountCommand,),
                               {'value': plasTeX.count(initial)})
        self.addGlobal(name, newclass)

    def newdimen(self, name, initial=0):
        """
        Create a new dimen (like \\newdimen)

        Required Arguments:
        name -- name of dimen to create

        Keyword Arguments:
        initial -- value to initialize to

        """
        name = str(name)
        # Generate a new dimen class
        macrolog.debug1('creating dimen %s', name)
        newclass = type(name, (plasTeX.DimenCommand,),
                                {'value': plasTeX.dimen(initial)})
        self.addGlobal(name, newclass)

    def newskip(self, name, initial=0):
        """
        Create a new glue (like \\newskip)

        Required Arguments:
        name -- name of glue to create

        Keyword Arguments:
        initial -- value to initialize to

        """
        name = str(name)
        # Generate a new glue class
        macrolog.debug1('creating dimen %s', name)
        newclass = type(name, (plasTeX.GlueCommand,),
                                {'value': plasTeX.glue(initial)})
        self.addGlobal(name, newclass)

    def newmuskip(self, name, initial=0):
        """
        Create a new muglue (like \\newmuskip)

        Required Arguments:
        name -- name of muglue to create

        Keyword Arguments:
        initial -- value to initialize to

        """
        name = str(name)
        # Generate a new muglue class
        macrolog.debug1('creating muskip %s', name)
        newclass = type(name, (plasTeX.MuGlueCommand,),
                                {'value': plasTeX.muglue(initial)})
        self.addGlobal(name, newclass)

    def newif(self, name, initial=False):
        """
        Create a new \\if (and accompanying) commands

        This method corresponds to TeX's \\newif command.

        Required Arguments:
        name -- name of the 'if' command.  This name should always
            start with the letters 'if'.

        Keyword Arguments:
        initial -- initial value of the 'if' command

        """
        name = str(name)
        # \if already exists
        if name in self:
            macrolog.debug('if %s already defined', name)
            return

        # Generate new 'if' class
        macrolog.debug1('creating if %s', name)
        ifclass = type(name, (plasTeX.NewIf,), {'state':initial})
        self.addGlobal(name, ifclass)

        # Create \iftrue macro
        truename = name[2:]+'true'
        newclass = type(truename, (plasTeX.IfTrue,), {'ifclass':ifclass})
        self.addGlobal(truename, newclass)

        # Create \iffalse macro
        falsename = name[2:]+'false'
        newclass = type(falsename, (plasTeX.IfFalse,), {'ifclass':ifclass})
        self.addGlobal(falsename, newclass)

    def newcommand(self, name, nargs=0, definition=None, opt=None):
        """
        Create a \\newcommand

        Required Arguments:
        name -- name of the macro to create
        nargs -- integer number of arguments that the macro has
        definition -- string containing the LaTeX definition
        opt -- string containing the LaTeX code to use in the
            optional argument

        Examples::
            c.newcommand('bold', 1, r'\\textbf{#1}')
            c.newcommand('foo', 2, r'{\\bf #1#2}', opt='myprefix')

        """
        name = str(name)
        # Macro already exists
        if name in self:
            if not issubclass(self[name], (plasTeX.NewCommand,
                                           plasTeX.Definition)):
                if not issubclass(self[name], plasTeX.TheCounter):
                    return
            macrolog.debug('redefining command "%s"', name)

        if nargs is None:
            nargs = 0
        assert isinstance(nargs, int), 'nargs must be an integer'

        if isinstance(definition, string_types):
            definition = [x for x in Tokenizer(definition, self)]

        if isinstance(opt, string_types):
            opt = [x for x in Tokenizer(opt, self)]

        macrolog.debug1('creating newcommand %s', name)
        newclass = type(name, (plasTeX.NewCommand,),
                       {'nargs':nargs,'opt':opt,'definition':definition})

        self.addGlobal(name, newclass)

    def newenvironment(self, name, nargs=0, definition=None, opt=None):
        """
        Create a \\newenvironment

        Required Arguments:
        name -- name of the macro to create
        nargs -- integer number of arguments that the macro has
        definition -- two-element tuple containing the LaTeX definition.
            Each element should be a string.  The first element
            corresponds to the beginning of the environment, and the
            second element is the end of the environment.
        opt -- string containing the LaTeX code to use in the
            optional argument

        Examples::
            c.newenvironment('mylist', 0, (r'\\begin{itemize}', r'\\end{itemize}'))

        """
        name = str(name)
        # Macro already exists
        if name in self:
            if not issubclass(self[name], (plasTeX.NewCommand,
                                           plasTeX.Definition)):
                return
            macrolog.debug('redefining environment "%s"', name)

        if nargs is None:
            nargs = 0
        assert isinstance(nargs, int), 'nargs must be an integer'

        if definition is not None:
            assert isinstance(definition, (tuple,list)), \
                'definition must be a list or tuple'
            assert len(definition) == 2, 'definition must have 2 elements'

            if isinstance(definition[0], string_types):
                definition[0] = [x for x in Tokenizer(definition[0], self)]
            if isinstance(definition[1], string_types):
                definition[1] = [x for x in Tokenizer(definition[1], self)]

        if isinstance(opt, string_types):
            opt = [x for x in Tokenizer(opt, self)]

        macrolog.debug1('creating newenvironment %s', name)

        # Begin portion
        newclass = type(name, (plasTeX.NewCommand,),
                       {'nargs':nargs,'opt':opt,'definition':definition[0]})
        self.addGlobal(name, newclass)

        # End portion
        newclass = type('end'+name, (plasTeX.NewCommand,),
                       {'nargs':0,'opt':None,'definition':definition[1]})
        self.addGlobal('end' + name, newclass)

    def newdef(self, name, args=None, definition=None, local=True):
        """
        Create a \def

        Required Arguments:
        name -- name of the macro to create
        args -- string containing the TeX argument profile
        definition -- string containing the LaTeX definition

        Keyword Arguments:
        local -- indicates whether this macro is local or global

        Examples::
            c.newdef('bold', '#1', '{\\bf #1}')
            c.newdef('put', '(#1,#2)#3', '\\dostuff{#1}{#2}{#3}')

        """
        name = str(name)
        # Macro already exists
#       if self.has_key(name):
#           if not issubclass(self[name], (plasTeX.NewCommand,
#                                          plasTeX.Definition)):
#               return
#           macrolog.debug('redefining definition "%s"', name)

        if isinstance(definition, string_types):
            definition = [x for x in Tokenizer(definition, self)]

        macrolog.debug1('creating def %s', name)
        newclass = type(name, (plasTeX.Definition,),
                       {'args':args,'definition':definition})

        if local:
            self.addLocal(name, newclass)
        else:
            self.addGlobal(name, newclass)

    def let(self, dest, source):
        """
        Create a \let

        Required Arguments:
        dest -- the command sequence to create
        source -- the token to set the command sequence equivalent to

        Examples::
            c.let('bgroup', BeginGroup('{'))

        """
        self.lets[dest] = source

    def chardef(self, name, num):
        """
        Create a \\chardef

        Required Arguments:
        name -- name of command to create
        num -- character number to use

        """
        name = str(name)
        # Generate a new chardef class
        macrolog.debug1('creating chardef %s', name)
        newclass = type(name, (plasTeX.Command,),
                        {'unicode':chr(num)})
        self.addGlobal(name, newclass)
