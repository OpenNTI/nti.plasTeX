#!/usr/bin/env python2.7

import os
import sys
import string
import datetime
import logging

import plasTeX
from plasTeX.TeX import TeX
from plasTeX.Logging import getLogger

import transforms
from zope.configuration import xmlconfig

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

	#setup config options we want
	document.config['files']['split-level'] = 1
	document.config['general']['theme'] = 'AoPS'
	# Read a config if present
	document.config.add_section( 'NTI' )
	document.config.set( 'NTI', 'provider', os.environ.get( 'NTI_PROVIDER', 'AOPS' ) )
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
	# the local Template being first
	xhtmltemplates = (os.path.join( os.getcwd(), 'Templates' ),
					  packages_path,
					  resource_filename( __name__, 'zpts' ),
					  os.environ.get('XHTMLTEMPLATES', ''))
	os.environ['XHTMLTEMPLATES'] = os.path.pathsep.join( xhtmltemplates )

	# Parse the document
	print "Parsing %s" % sourceFile
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
		print "Generating images"
		db = generateImages(document)

	if outFormat == 'xhtml':
		render( document, 'XHTML', db )
		postRender(document, jobname=jobname)

	if outFormat == 'xml':
		toXml( document, jobname )

def nextID(self):
	ntiid = getattr(self, 'NTIID',-1)

	ntiid = ntiid + 1

	setattr(self, 'NTIID', ntiid)
	provider = self.config.get( "NTI", "provider" )
	return 'tag:nextthought.com,2011-10:%s-HTML-%s.%s' % (provider,self.userdata['jobname'], ntiid)

plasTeX.TeXDocument.nextNTIID = nextID

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
	print 'Performing post render steps'

	# We very likely will get a book that has no pages
	# because NTIIDs are not added yet.
	book = RenderedBook(document, contentLocation)

	# This step adds NTIIDs to the TOC in addition to modifying
	# on-disk content.
	print 'Adding icons to toc and pages'
	toc_file = os.path.join(contentLocation, 'eclipse-toc.xml')
	tociconsetter.transform(book)

	print 'Fetching page info'
	book = RenderedBook(document, contentLocation)

	print 'Storing content height in pages'
	contentsizesetter.transform(book)

	print 'Adding related links to toc'
	relatedlinksetter.performTransforms(book)

	print 'Generating thumbnails for pages'
	contentthumbnails.transform(book)

	# PhantomJS doesn't cope well with the iframes
	# for embedded videos: you get a black box, and we put them at the top
	# of the pages, so many thumbnails end up looking the same, and looking
	# bad. So do this after taking thumbnails.
	print 'Adding videos'
	sectionvideoadder.performTransforms(book)

	print 'Running checks on content'
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
	print "Creating html cache-manifest"
	html5cachefile.main(contentPath, contentPath)

	print 'Changing intra-content links'
	ntiidlinksetter.transform( book )

	print "Creating a mirror file"
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
