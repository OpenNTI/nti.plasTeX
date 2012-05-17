#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
$Id$
"""
from __future__ import print_function, unicode_literals


import os
import sys
import string
import datetime
import logging
import hashlib

import plasTeX
from plasTeX.TeX import TeX
from plasTeX.Logging import getLogger

import transforms
from zope.configuration import xmlconfig
from zope.deprecation import deprecate

import nti.contentrendering

from pkg_resources import resource_filename

log = getLogger(__name__)
logger = log


def _configure_logging():
	logging.basicConfig( level=logging.INFO )
	logging.root.handlers[0].setFormatter( logging.Formatter( '[%(name)s] %(levelname)s: %(message)s' ) )

def main():
	""" Main program routine """
	argv = sys.argv[1:]
	_configure_logging()
	xmlconfig.file( 'configure.zcml', package=nti.contentrendering )

	sourceFile = argv.pop(0)
	source_dir = os.path.dirname( os.path.abspath( os.path.expanduser( sourceFile ) ) )

	outFormat = 'xml'
	if argv:
		outFormat = argv.pop(0)

	# Set up imports for style files. The preferred, if verbose, way is to
	# use a fully qualified python name. But for legacy and convenience
	# reasons, we support non-qualified imports (if the module does)
	# by adding that directory directly to the path
	# Note that the cwd is on the path by default and files there
	# (per-job) should take precedence
	packages_path = os.path.join( os.path.dirname( __file__ ) , 'plastexpackages' )
	sys.path.append( packages_path )


	# Create document instance that output will be put into
	document = plasTeX.TeXDocument()

	#setup default config options we want
	document.config['files']['split-level'] = 1
	document.config['document']['toc-depth'] = sys.maxint # Arbitrary number greater than the actual depth possible
	document.config['document']['toc-non-files'] = True
	# By outputting in ASCII, we are still valid UTF-8, but we use
	# XML entities for high characters. This is more likely to survive
	# through various processing steps that may not be UTF-8 aware
	document.config['files']['output-encoding'] = 'ascii'
	document.config['general']['theme'] = 'NTIDefault'
	document.config['general']['theme-base'] = 'NTIDefault'
	# Read a config if present
	document.config.add_section( 'NTI' )
	document.config.set( 'NTI', 'provider', os.environ.get( 'NTI_PROVIDER', 'AOPS' ) )
	document.config.set( 'NTI', 'extra-scripts', '' )
	document.config.set( 'NTI', 'extra-styles', '' )
	conf_name = os.path.join( source_dir, "nti_render_conf.ini" )
	document.config.read( (conf_name,) )

	# Configure components and utilities
	zope_conf_name = os.path.join( source_dir, 'configure.zcml' )
	if os.path.exists( zope_conf_name ):
		xmlconfig.file( zope_conf_name, package=nti.contentrendering )

	# Instantiate the TeX processor
	tex = TeX(document, file=sourceFile)

	# Populate variables for use later
	jobname = document.userdata['jobname'] = tex.jobname
	document.userdata['working-dir'] = os.getcwd()
	document.userdata['generated_time'] = str(datetime.datetime.now())
	document.userdata['transform_process'] = True

	document.userdata['extra_scripts'] = document.config['NTI']['extra-scripts'].split()
	document.userdata['extra_styles'] = document.config['NTI']['extra-styles'].split()

	setupResources()

	# Load aux files for cross-document references
	# pauxname = '%s.paux' % jobname

	# for dirname in [cwd] + config['general']['paux-dirs']:
	#	for fname in glob.glob(os.path.join(dirname, '*.paux')):
	#		if os.path.basename(fname) == pauxname:
	#			continue
	#		document.context.restore(fname, rname)


	# Set up TEXINPUTS to include the current directory for the renderer,
	# plus our packages directory
	texinputs = (os.getcwd(), source_dir, packages_path, os.environ.get('TEXINPUTS', ''))
	os.environ['TEXINPUTS'] = os.path.pathsep.join( texinputs )

	# Likewise for the renderers, with the addition of the legacy 'zpts' directory.
	# Parts of the code (notably tex2html._find_theme_mathjaxconfig) depend on
	# the local Template being first. Note that earlier values will take precedence
	# over later values.
	xhtmltemplates = (os.path.join( os.getcwd(), 'Templates' ),
					  packages_path,
					  resource_filename( __name__, 'zpts' ),
					  os.environ.get('XHTMLTEMPLATES', ''))
	os.environ['XHTMLTEMPLATES'] = os.path.pathsep.join( xhtmltemplates )
	# Set up a cache for these things to make subsequent renders faster
	if not 'CHAMELEON_CACHE' in os.environ:
		parent = os.getcwd()
		for p in ('DATASERVER_ENV','DATASERVER_DIR','VIRTUAL_ENV'):
			if p in os.environ:
				parent = os.environ[p]
				break
		os.environ['CHAMELEON_CACHE'] = os.path.join( parent, '.chameleon_cache' )
		logger.info( "Caching templates to %s", os.environ['CHAMELEON_CACHE'] )
		try:
			os.mkdir( os.environ['CHAMELEON_CACHE'] )
		except OSError: pass

	# Parse the document
	logger.info( "Parsing %s", sourceFile )
	tex.parse()

	# Change to specified directory to output to
	outdir = document.config['files']['directory']
	if outdir:
		outdir = string.Template(outdir).substitute({'jobname':jobname})
		if not os.path.isdir(outdir):
			os.makedirs(outdir)
		log.info('Directing output files to directory: %s.' % outdir)
		os.chdir(outdir)

	# Perform prerender transforms
	transforms.performTransforms( document )

	if outFormat == 'images' or outFormat == 'xhtml':
		logger.info( "Generating images" )
		db = generateImages(document)

	if outFormat == 'xhtml':
		render( document, 'XHTML', db )
		postRender(document, jobname=jobname)

	if outFormat == 'xml':
		toXml( document, jobname )

@deprecate("Prefer the section element ntiid attribute")
def nextID(self):
	ntiid = getattr(self, 'NTIID', -1)

	ntiid = ntiid + 1

	setattr(self, 'NTIID', ntiid)
	provider = self.config.get( "NTI", "provider" )
	return 'tag:nextthought.com,2011-10:%s-HTML-%s.%s' % (provider,self.userdata['jobname'], ntiid)

plasTeX.TeXDocument.nextNTIID = nextID

# SectionUtils is the (a) parent of chapter, section, ..., paragraph, as well as document
from plasTeX.Base.LaTeX.Sectioning import SectionUtils
def _section_ntiid(self):

	if hasattr(self,"@NTIID"):
		return getattr(self, "@NTIID")

	document = self.ownerDocument
	config = document.config
	# Use an ID if it exists and WAS NOT generated
	# (see plasTeX/__init__.py; also relied on in Renderers/__init__.py)
	if not hasattr( self, "@hasgenid" ) and getattr( self, "@id", None ):
		local = getattr( self, "@id" )
	elif self.title and getattr(self.title, 'textContent', self.title):
		# Sometimes title is a string, sometimes its a TexFragment
		title = self.title
		if hasattr(self.title, 'textContent'):
			title = self.title.textContent
		_section_ntiids_map = document.userdata.setdefault( '_section_ntiids_map', {} )
		counter = _section_ntiids_map.setdefault( title, 0 )
		if counter == 0:
			local = title
		else:
			local = title + '.' + str(counter)
		_section_ntiids_map[title] = counter + 1
	else:
		# Hmm. An untitled element that is also not
		# labeled. This is most likely a paragraph. What can we do for a persistent
		# name? Does it even matter?
		setattr(self, "@NTIID", nextID(document))
		return getattr(self, "@NTIID")

	# TODO: This is a half-assed approach to escaping
	local = local.replace( ' ', '_' ).replace( '-', '_' ).replace('?','_').lower()
	provider = config.get( "NTI", "provider" )
	ntiid = 'tag:nextthought.com,2011-10:%s-HTML-%s.%s' % (provider,document.userdata['jobname'], local)
	setattr( self, "@NTIID", ntiid )
	return ntiid

def _section_ntiid_filename(self):
	if not hasattr(self, 'config'):
		return

	level = getattr(self, 'splitlevel',	self.config['files']['split-level'])

	# If our level doesn't invoke a split, don't return a filename
	# (This is duplicated from Renderers)
	if self.level > level:
		return
	# It's confusing to have the filenames be valid
	# URLs (tag:) themselves. Escaping is required, but doesn't happen.
	return self.ntiid.replace( ':', '_' ) if self.ntiid else None

def catching(f):
	def y(self):
		try:
			return f(self)
		except Exception:
			logger.exception("Failed to compute NTIID for %s", self )
			raise
	return y

SectionUtils.ntiid = property(catching(_section_ntiid))
SectionUtils.filenameoverride = property(catching(_section_ntiid_filename))
# Certain things like to assume that the root document is called index.html. Make it so.
# This is actuall plasTeX.Base.LaTeX.Document.document, but games are played
# with imports. damn it.
plasTeX.Base.document.filenameoverride = property(lambda s: 'index') #.html added automatically

# Attempt to generate stable IDs for paragraphs. Our current approach
# is to use a hash of the source. This is very, very fragile to changes
# in the text, but works well for reorganizing content. We should probably try to do
# something like a Soundex encoding
def _par_id_get(self):
	_id = getattr( self, "@id", self )
	if _id is not self: return _id

	if self.isElementContentWhitespace or not self.source.strip():
		return None

	document = self.ownerDocument
	source = self.source
	# A fairly common case is to have a label as a first child (maybe following some whitespace); in that case,
	# for all intents and purposes (in rendering) we want our external id to be the same
	# as the label value. However, we don't want to duplicate IDs in the DOM
	first_non_blank_child = None
	for child in self.childNodes:
		first_non_blank_child = child
		if child.nodeType != child.TEXT_NODE or child.textContent.strip():
			break

	if first_non_blank_child.nodeName == 'label' and 'label' in first_non_blank_child.attributes:
		setattr( self, "@id", None )
		return None

	if source and source.strip():
		_id = hashlib.md5(source.strip().encode('utf-8')).hexdigest()
	else:
		counter = document.userdata.setdefault( '_par_counter', 1 )
		_id = 'p%10d' % counter
		document.userdata['_par_counter'] = counter + 1

	used_pars = document.userdata.setdefault( '_par_used_ids', set() )
	while _id in used_pars:
		counter = document.userdata.setdefault( '_par_counter', 1 )
		_id = _id + '.' + str(counter)
		document.userdata['_par_counter'] = counter + 1
	used_pars.add( _id )

	setattr( self, "@id", _id )
	setattr( self, "@hasgenid", True )
	return _id

plasTeX.Base.par.id = property(_par_id_get,plasTeX.Base.par.id.fset)



import mirror
import indexer
import tociconsetter
import html5cachefile
import contentsizesetter
import relatedlinksetter
import contentthumbnails
import sectionvideoadder
import ntiidlinksetter

from RenderedBook import RenderedBook

import contentchecks
import subprocess

def postRender(document, contentLocation='.', jobname='prealgebra'):
	logger.info( 'Performing post render steps' )

	# We very likely will get a book that has no pages
	# because NTIIDs are not added yet.
	book = RenderedBook(document, contentLocation)

	# This step adds NTIIDs to the TOC in addition to modifying
	# on-disk content.
	logger.info( 'Adding icons to toc and pages' )
	toc_file = os.path.join(contentLocation, 'eclipse-toc.xml')
	tociconsetter.transform(book)

	logger.info( 'Fetching page info' )
	book = RenderedBook(document, contentLocation)

	logger.info( 'Storing content height in pages' )
	contentsizesetter.transform(book)

	logger.info( 'Adding related links to toc' )
	relatedlinksetter.performTransforms(book)

	logger.info( 'Generating thumbnails for pages' )
	contentthumbnails.transform(book)

	# PhantomJS doesn't cope well with the iframes
	# for embedded videos: you get a black box, and we put them at the top
	# of the pages, so many thumbnails end up looking the same, and looking
	# bad. So do this after taking thumbnails.
	logger.info( 'Adding videos' )
	sectionvideoadder.performTransforms(book)

	logger.info( 'Running checks on content' )
	contentchecks.performChecks(book)

	contentPath = os.path.realpath(contentLocation)
	if not os.path.exists( os.path.join( contentPath, 'indexdir' ) ):
		# Try with pypy, it's much faster
		env = dict(os.environ)
		# Need whoosh, etc, on the path, but NOT the standard lib, or the
		# raw site-packages (so no site.py). This requires whoosh to be
		# installed as an egg using easy_intstall.pth. Note that rejecting
		# the standard lib is only required if we're not
		# in a virtual environment.
		def try_pypy( in_virtual_env=True ):
			if in_virtual_env:
				path = [p for p in sys.path if not p.startswith( '/opt' )]
			else:
				path = [p for p in sys.path
						if not p.endswith('site-packages') and not p.endswith('site-packages/') and not p.endswith('python2.7')]
			env['PYTHONPATH'] = ':'.join(path)

			logger.info( 'Indexing content with pypy' )
			subprocess.check_call( ['pypy-c', '-m', 'nti.contentrendering.indexer',
									toc_file, contentPath, 'indexdir', jobname],
									env=env )

		try:
			try_pypy()
		except (subprocess.CalledProcessError,OSError):
			logger.info( "pypy virtualenv failed; trying system" )
			try:
				try_pypy( False )
			except (subprocess.CalledProcessError,OSError):
				logger.info( 'pypy failed to index, falling back to current' )
				logger.debug( 'pypy exception', exc_info=True )
				indexer.index_content(tocFile=toc_file, contentPath=contentPath, indexname=jobname)

	# TODO: Aren't the things in the archive mirror file the same things
	# we want to list in the manifest? If so, we should be able to combine
	# these steps (if nothing else, just list the contents of the archive to get the
	# manifest)
	logger.info( "Creating html cache-manifest" )
	html5cachefile.main(contentPath, contentPath)

	logger.info( 'Changing intra-content links' )
	ntiidlinksetter.transform( book )

	logger.info( "Creating a mirror file" )
	mirror.main( contentPath, contentPath, zip_root_dir=jobname )


from resources.ResourceRenderer import createResourceRenderer

def render(document, rname, db):
	# Apply renderer
	renderer = createResourceRenderer(rname, db)
	renderer.render(document)

def toXml( document, jobname ):
	outfile = '%s.xml' % jobname
	with open(outfile,'w') as f:
		f.write(document.toXML().encode('utf-8'))

from resources import ResourceDB, ResourceTypeOverrides

def setupResources():
	from plasTeX.Base import Arrays
	tabularTypes = ['png', 'svg']

	Arrays.tabular.resourceTypes = tabularTypes
	Arrays.TabularStar.resourceTypes = tabularTypes
	Arrays.tabularx.resourceTypes = tabularTypes

	from plasTeX.Base import Math

	#The math package does not correctly implement the sqrt macro.	It takes two args
	Math.sqrt.args = '[root]{arg}'

	inlineMathTypes = ['mathjax_inline']
	displayMathTypes = ['mathjax_display']

	#inlineMathTypes = ['mathjax_inline', 'png', 'svg']
	#displayMathTypes = ['mathjax_display', 'png', 'svg']

	Math.math.resourceTypes = inlineMathTypes
	Math.ensuremath.resourceTypes = inlineMathTypes

	Math.displaymath.resourceTypes = displayMathTypes
	Math.EqnarrayStar.resourceTypes = displayMathTypes
	Math.equation.resourceTypes = displayMathTypes


	from plasTeX.Packages.graphicx import includegraphics
	includegraphics.resourceTypes = ['png']

	from plasTeX.Packages import amsmath
	amsmath.align.resourceTypes = displayMathTypes
	amsmath.AlignStar.resourceTypes = displayMathTypes
	amsmath.alignat.resourceTypes = displayMathTypes
	amsmath.AlignatStar.resourceTypes = displayMathTypes
	amsmath.gather.resourceTypes = displayMathTypes
	amsmath.GatherStar.resourceTypes = displayMathTypes

	# XXX FIXME If we don't do this, then we can get
	# a module called graphicx reloaded from this package
	# which doesn't inherit our type. Who is doing that?
	sys.modules['graphicx'] = sys.modules['plasTeX.Packages.graphicx']

	#includegraphics.resourceTypes = ['png', 'svg']

def generateImages(document):
	### Generates required images ###
	# Replace this with configuration/use of ZCA?
	local_overrides = os.path.join( os.getcwd(), 'nti.resourceoverrides', ResourceTypeOverrides.OVERRIDE_INDEX_NAME )
	if os.path.exists( local_overrides ):
		overrides = local_overrides
	else:
		overrides = resource_filename(__name__, 'resourceoverrides')
	db = ResourceDB(document, overridesLocation=overrides)
	db.generateResourceSets()
	return db
