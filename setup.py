#!/usr/bin/env python

#from distutils.core import setup
from setuptools import setup, find_packages


import platform
py_impl = getattr(platform, 'python_implementation', lambda: None)
IS_PYPY = py_impl() == 'PyPy'


entry_points = {
	'console_scripts': [
		'plastex = plasTeX.plastex:main'
	]
}

templates = ['*.html','*.htm','*.xml','*.zpt','*.zpts']
images = ['*.gif','*.png','*.jpg','*.jpeg','*.js','*.htc']
styles = ['*.css']

TESTS_REQUIRE = [
	'beautifulsoup4 >= 4.3.1',
	'blessings >= 1.5.1',  # A thin, practical wrapper around terminal coloring, styling, and positioning. Pulled in by nose-progressive(?)
	'coverage >= 3.6',  # Test coverage
	'fudge >= 1.0.3',
	'nose >= 1.3.0',
	'nose-timer >= 0.1.2',
	'nose-progressive >= 1.5',
	'pyhamcrest >= 1.7.2',
	# 'z3c.coverage >= 2.0.0', # For HTML coverage reports that are prettier than plain 'coverage' TODO: Do we need this?
	#'zope.testing >= 4.1.2',
	'nti.nose_traceback_info',
]

INSTALL_REQUIRES = [
	'Chameleon >= 2.12',  # (preferred) template rendering. pulled in by pyramid, but ensure latest version

	# PIL is currently (as of 2012-07) at version 1.1.7 (from 2009), which
	# is the version that Pillow forked from in 2010 as version 1.0. So
	# Pillow is currently way ahead of PIL. Pillow 2 is Python 3 compatible (and partly pypy)
	# includes transparent png support, and is much cleaned up, otherwise api compatible with pillow 1/PIL 1
	'Pillow >= 2.1.0',

	'z3c.pt >= 3.0.0a1',  # Better ZPT support than plastex, add-in to Chameleon
	'z3c.ptcompat >= 2.0.0a1',  # Make zope.pagetemplate also use the Chameleon-based ZPT
	'z3c.table >= 2.0.0a1',  # Flexible table rendering

	'zope.cachedescriptors >= 4.0.0',

	'zope.component >= 4.1.0',
	'zope.configuration >= 4.0.2',
	'zope.contentprovider >= 4.0.0a1',
	'zope.contenttype >= 4.0.1',  # A utility module for content-type handling.
	'zope.dottedname',
	'zope.dublincore >= 4.0.0',
	'zope.error >= 4.1.0',
	'zope.event >= 4.0.2',
	'zope.exceptions >= 4.0.6',
	'zope.filerepresentation >= 4.0.2',
#	'zope.file >= 0.6.2' if HAVE_ZCONT else '',  # zope.container dep
	'zope.formlib >= 4.3.0a1',  # Req'd by zope.mimetype among others,
	'zope.hookable >= 4.0.1',  # explicitly list this to ensure we get the fast C version. Used by ZCA.
	'zope.i18n >= 4.0.0a4',
	'zope.i18nmessageid >= 4.0.2',
	'zope.interface >= 4.0.5',
	'zope.lifecycleevent >= 4.0.2',  # Object Added/Removed/etc events
	'zope.location >= 4.0.2',
	'zope.mimetype == 1.3.1',  # freeze on 1.3.1 pending 2.0.0a2, https://github.com/zopefoundation/zope.mimetype/pull/1
	'zope.pagetemplate >= 4.0.4',
#	'zope.ptresource >= 4.0.0a1',
#	'zope.publisher >= 4.0.0a4',
	'zope.proxy >= 4.1.3',  # 4.1.x support py3k, uses newer APIs. Not binary compat with older extensions, must rebuild. (In partic, req zope.security >= 3.9)
	'zope.schema >= 4.3.2',
	'zope.security[zcml,untrustedpython] >= 4.0.0',  # >= 4.0.0b1 gets PyPy support!
	# parser and renderers for the classic Zope "structured text" markup dialect (STX).
	# STX is a plain text markup in which document structure is signalled primarily by identation.
	# Pulled in by ...?
	#'zope.structuredtext >= 4.0.0',
	'zope.tal >= 4.0.0a1',
	'zope.tales >= 4.0.1',
	'zope.traversing >= 4.0.0a3',
	# Plug to make zope.schema's vocabulary registry ZCA
	# based and thus actually useful
	'zope.vocabularyregistry >= 1.0.0',
]

setup(name="nti.plasTeX",
      description="LaTeX document processing framework",
      version="0.9.3",
      author="Kevin D. Smith",
      author_email="Kevin.Smith@sas.com",
	  tests_require=TESTS_REQUIRE,
	  install_requires=INSTALL_REQUIRES,
	  packages=find_packages('src'),
	  package_dir={'': 'src'},
	  include_package_data=True,
	  #namespace_packages=['nti', ],
	  zip_safe=False,
	  entry_points=entry_points,
      package_data = {
         'plasTeX': ['*.xml'],
         'plasTeX.Base.LaTeX': ['*.xml','*.txt'],
         'plasTeX.Renderers.DocBook': templates,
         'plasTeX.Renderers.DocBook.Themes.default': templates,
         'plasTeX.Renderers.DocBook.Themes.book': templates,
         'plasTeX.Renderers.DocBook.Themes.article': templates,
         'plasTeX.Renderers.XHTML': templates,
         'plasTeX.Renderers.XHTML.Themes.default': templates,
         'plasTeX.Renderers.XHTML.Themes.default.icons': images,
         'plasTeX.Renderers.XHTML.Themes.default.styles': styles,
         'plasTeX.Renderers.XHTML.Themes.python': templates+styles,
         'plasTeX.Renderers.XHTML.Themes.python.icons': images,
         'plasTeX.Renderers.XHTML.Themes.plain': templates,
         'plasTeX.Renderers.S5': templates,
         'plasTeX.Renderers.S5.Themes.default': templates,
         'plasTeX.Renderers.S5.Themes.default.ui.default': templates+styles+images,
      },
	  extras_require={
		  'test': TESTS_REQUIRE,
		  'tools': [
			'ipython >= 1.0.0',  # the extra notebook is web based, pulls in tornado
			'logilab_astng >= 0.24.3',
			'pip >= 1.3.1',
			'pip-tools >= 0.3.4',  # command pip-review, pip-dump
			'pudb >= 2013.2',  # Python full screen console debugger. Beats ipython's: import pudb; pdb.set_trace()
			'pylint >= 1.0.0' if not IS_PYPY else '',
			'readline >= 6.2.4.1' if not IS_PYPY else '',
			'repoze.sphinx.autointerface >= 0.7.1',
			'rope >= 0.9.4',  # refactoring library. c.f. ropemacs
			'ropemode >= 0.2',  # IDE helper for rope
			'sphinx >= 1.2b1',  # Narrative docs
			'sphinxcontrib-programoutput >= 0.8',
			'sphinxtheme.readability >= 0.0.6',
			'virtualenv >= 1.10.1',
			'virtualenvwrapper >= 4.0',
			'zc.buildout >= 2.1.0',
			'z3c.dependencychecker >= 1.11',  # unused/used imports; see also tl.eggdeps
			# Managing translations
			'Babel >= 1.3',
			'lingua >= 1.5',
			]
		},
		dependency_links=[
			'git+https://github.com/NextThought/nti.nose_traceback_info.git#egg=nti.nose_traceback_info'
		],
)
