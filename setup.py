#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages
from os.path import join, dirname
import platform
py_impl = getattr(platform, 'python_implementation', lambda: None)
IS_PYPY = py_impl() == 'PyPy'
IS_JYTHON = py_impl() == 'Jython'


entry_points = {
    'console_scripts': [
        'plastex = plasTeX.plastex:main'
    ]
}

TESTS_REQUIRE = [
    'beautifulsoup4',
    'fudge',
    'nose',
    # nose-progressive breaks under py33
    #'nose-progressive >= 1.5',
    'pyhamcrest',
    'nti.nose_traceback_info'
]

INSTALL_REQUIRES = [
    'Chameleon',  # (preferred) template rendering. pulled in by pyramid, but ensure latest version

    # PIL is currently (as of 2012-07) at version 1.1.7 (from 2009), which
    # is the version that Pillow forked from in 2010 as version 1.0. So
    # Pillow is currently way ahead of PIL. Pillow 2 is Python 3 compatible (and partly pypy)
    # includes transparent png support, and is much cleaned up, otherwise api compatible with pillow 1/PIL 1
    'Pillow',

    'six',

    'z3c.pt >= 3.0.0a1',  # Better ZPT support than plastex, add-in to Chameleon
    'z3c.ptcompat >= 2.0.0a1',  # Make zope.pagetemplate also use the Chameleon-based ZPT
    'zope.annotation',
    'zope.cachedescriptors >= 4.0.0',

    'zope.component',
    'zope.configuration',
    'zope.dottedname',
    'zope.dublincore',
    'zope.error',
    'zope.event >= 4.0.2',
    'zope.exceptions',
    'zope.hookable >= 4.0.1',  # explicitly list this to ensure we get the fast C version. Used by ZCA.
    'zope.i18n >= 4.0.0a4',
    'zope.i18nmessageid >= 4.0.2',
    'zope.interface',
    'zope.location',
    'zope.pagetemplate >= 4.0.4',
#   'zope.ptresource >= 4.0.0a1',
#   'zope.publisher >= 4.0.0a4',
    'zope.proxy',  # 4.1.x support py3k, uses newer APIs. Not binary compat with older extensions, must rebuild. (In partic, req zope.security >= 3.9)
    'zope.tal >= 4.0.0a1',
    'zope.tales >= 4.0.1',
    'zope.traversing >= 4.0.0a3',
]

def read(name, *args):
    try:
        with open(join(dirname(__file__), name)) as f:
            return f.read(*args)
    except OSError:
        return ''


setup(name="nti.plasTeX",
      description="LaTeX document processing framework",
      long_description=read('README.rst'),
      version="0.9.3",
      author="Kevin D. Smith",
      author_email="Kevin.Smith@sas.com",
      tests_require=TESTS_REQUIRE,
      install_requires=INSTALL_REQUIRES,
      classifiers=[
          "Development Status :: 4 - Beta",
          "Operating System :: POSIX :: Linux",
          "Programming Language :: Python :: 2.7",
          "Programming Language :: Python :: 3.3",
          "Programming Language :: Python :: 3.4",
          "Programming Language :: Python :: Implementation :: CPython",
          "Programming Language :: Python :: Implementation :: PyPy",
          "Programming Language :: Python :: Implementation :: Jython",
          "Operating System :: MacOS :: MacOS X",
          "Framework :: Zope3",
      ],
      packages=find_packages('src'),
      package_dir={'': 'src'},
      include_package_data=True,
      zip_safe=False,
      entry_points=entry_points,
      setup_requires = [
           # Without this, we don't get data files in sdist,
           # which in turn means tox can't work
          'setuptools-git'
      ],
      extras_require={
          'test': TESTS_REQUIRE,
          'tools': [
            'repoze.sphinx.autointerface >= 0.7.1',
            'sphinx >= 1.2b1',  # Narrative docs
            ]
        },
        dependency_links=[
        ],
)
