
from __future__ import print_function, unicode_literals, absolute_import, division


import os, sys, codecs, string, glob
import plasTeX
from plasTeX.TeX import TeX
from plasTeX.Config import newConfig

from plasTeX.Logging import getLogger
from zope.configuration import xmlconfig

log = getLogger()

__version__ = '0.9.3'

def main():
	""" Main program routine """
	print( 'plasTeX version %s' % __version__, file=sys.stderr )

	argv = sys.argv
	xml_conf_context = xmlconfig.file('configure.zcml', package=plasTeX)
	# Parse the command line options
	config = newConfig()
	try:
		opts, args = config.getopt(argv[1:])
	except Exception as msg:
		log.error(msg)
		print( config.usage(), file=sys.stderr )
		sys.exit(1)

	if not args:
		print( config.usage(), file=sys.stderr )
		sys.exit(1)

	tex_file = args.pop(0)

	# Create document instance that output will be put into
	document = plasTeX.TeXDocument(config=config)

	# Instantiate the TeX processor and parse the document
	tex = TeX(document, file=tex_file)

	# Populate variables for use later
	if config['document']['title']:
		document.userdata['title'] = config['document']['title']
	jobname = document.userdata['jobname'] = tex.jobname
	cwd = document.userdata['working-dir'] = os.getcwd()

	# Load aux files for cross-document references
	pauxname = '%s.paux' % jobname
	rname = config['general']['renderer']
	for dirname in [cwd] + config['general']['paux-dirs']:
		for fname in glob.glob(os.path.join(dirname, '*.paux')):
			if os.path.basename(fname) == pauxname:
				continue
			document.context.restore(fname, rname)

	# Parse the document
	tex.parse()

	# Set up TEXINPUTS to include the current directory for the renderer
	os.environ['TEXINPUTS'] = '%s%s%s%s' % (os.getcwd(), os.pathsep,
										 os.environ.get('TEXINPUTS',''), os.pathsep)

	# Change to specified directory to output to
	outdir = config['files']['directory']
	if outdir:
		outdir = string.Template(outdir).substitute({'jobname':jobname})
		if not os.path.isdir(outdir):
			os.makedirs(outdir)
		log.info('Directing output files to directory: %s.', outdir)
		os.chdir(outdir)

	# Load renderer
	try:
		exec('from plasTeX.Renderers.%s import Renderer' % rname)
	except ImportError, msg:
		log.error('Could not import renderer "%s"	Make sure that it is installed correctly, and can be imported by Python.', rname)
		sys.exit(1)

	# Write expanded source file
	#sourcefile = '%s.source' % jobname
	#open(sourcefile,'w').write(document.source.encode('utf-8'))

	# Write XML dump
	if config['general']['xml']:
		outfile = '%s.xml' % jobname
		codecs.open(outfile,'w',encoding='utf-8').write(document.toXML())

	# Apply renderer
	Renderer().render(document)

	print("")
