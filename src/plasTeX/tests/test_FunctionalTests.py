#!/usr/bin/env python
from __future__ import print_function

import os
import tempfile
import shutil
import difflib
import subprocess
import unittest

from . import skip_if_no_binaries
from . import run_plastex

class _ComparisonBenched(object):
    """ Compile LaTeX file and compare to benchmark file """

    class DontCleanupError(OSError):
        pass

    additional_renderers = (('.txt', 'Text'),
                            ('.docbook', 'DocBook'))

    def __call__(self, latex_file):
        __traceback_info__ = latex_file
        if not latex_file:
            return

        # Create temp dir and files
        outdir = tempfile.mkdtemp()
        clean_up = True
        try:
            self._compare(outdir, latex_file)
        except self.DontCleanupError:
            clean_up = False
            raise
        finally:
            # Clean up
            if clean_up:
                shutil.rmtree(outdir, ignore_errors=True)

    def __preprocess_file(self, outdir, original_source_file):
        root = os.path.dirname(os.path.dirname(original_source_file))

        # Run preprocessing commands
        with open(original_source_file, 'r') as f:
            for line in f:
                if line.startswith('%*'):
                    command = line[2:].strip()
                    subprocess.check_call(cwd=outdir, *command.split())
                elif line.startswith('%#'):
                    filename = line[2:].strip()
                    shutil.copyfile(os.path.join(root,'extras',filename),
                                    os.path.join(outdir,filename))
                elif line.startswith('%'):
                    continue
                elif not line.strip():
                    continue
                else:
                    break

    def __run_plastex(self, outdir, outfile, original_source_file, renderer=None):
        args = (
            '--split-level=0','--no-theme-extras',
            '--theme=minimal',
            '--filename=%s' % os.path.basename(outfile)
        )
        if renderer:
            args += ('--renderer=' + renderer, )
        return run_plastex(outdir, os.path.basename(original_source_file),
                           cwd=outdir,
                           args=args)

    def __no_benchmark_file(self, outdir, outfile, benchfile):
        raise self.DontCleanupError( 'No benchmark file: %s; new file in %s' % (benchfile, outfile) )

    def __differences_found(self, outdir, outfile, benchfile, diff):
        raise self.DontCleanupError('Diff between benchmark file (%s) and new file (%s):\n%s'
                                    % (benchfile, outfile, diff))

    def __compare(self, outdir, outfile, benchfile):
        # Get name of output file / benchmark file

        if not os.path.isfile(benchfile):
            # Don't cleanup, let the user compare/copy the benchfile into place
            return self.__no_benchmark_file(outdir, outfile, benchfile)


        with open(benchfile, 'r') as f:
            benchlines = f.readlines()
        with open(outfile, 'r') as f:
            outputlines = f.readlines()

        # Compare files
        diff = ''.join(list(difflib.unified_diff(benchlines, outputlines))).strip()
        if diff:
            # Don't cleanup, let the user decide to copy the new file into place
            self.__differences_found(outdir, outfile, benchfile, diff)

    def _compare(self, outdir, original_source_file):
        orig_root = os.path.dirname(os.path.dirname(original_source_file))

        basename = os.path.splitext(os.path.basename(original_source_file))[0]

        outfile = os.path.join(outdir, basename + '.html')

        benchfile = os.path.join(orig_root, 'benchmarks', os.path.basename(outfile))

        temp_latex_file = os.path.join(outdir, os.path.basename(original_source_file))

        shutil.copyfile(original_source_file, temp_latex_file)

        self.__preprocess_file(outdir, original_source_file)

        # Run plastex
        log = self.__run_plastex(outdir, outfile, original_source_file)

        # Read output file
        __traceback_info__ = log, outdir, outfile

        self.__compare(outdir, outfile, benchfile)

        eclipse_benchfile = os.path.join(orig_root, 'benchmarks', basename + '-eclipse-toc.xml')
        eclipse_outfile = os.path.join(outdir, 'eclipse-toc.xml')

        self.__compare(outdir, eclipse_outfile, eclipse_benchfile)

        # Now try to run the other renderers
        for ext, renderer in self.additional_renderers:
            outfile = os.path.join(outdir, basename + ext)
            benchfile = os.path.join(orig_root, 'benchmarks', os.path.basename(outfile))
            log = self.__run_plastex(outdir, outfile, original_source_file,
                                     renderer=renderer)
            __traceback_info__ = log, outdir, outfile
            self.__compare(outdir, outfile, benchfile)


def testSuite():
    """
    Test-generator for use with nose. Finds all .tex files beside/benath
    us and runs a matching comparison on them.
    """
    for root, _dirs, files in os.walk( os.path.dirname( __file__ ) ):
        for f in files:
            if os.path.splitext(f)[-1] != '.tex':
                continue

            __traceback_info__ = root, f
            yield _ComparisonBenched(), os.path.abspath(os.path.join(root, f))

def load_tests(testloader, module_suite, _):
    """
    Plain unittest/zope.testrunner compatible version of testSuite.
    """

    class RenderingLayer(object):
        """
        To mark a test that runs file based renders, slowly.
        """

    try:
        skip_if_no_binaries()
    except unittest.SkipTest:
        has_binaries = False
    else:
        has_binaries = True

    suite = unittest.TestSuite()
    class CompTestCase(unittest.TestCase):
        level = 2 # These are slow
        layer = RenderingLayer
        additional_renderers = _ComparisonBenched.additional_renderers

        def __init__(self, filename):
            unittest.TestCase.__init__(self)
            self.__filename = filename
            self.__name__ = filename

        def runTest(self): #magic unitest method name
            c = _ComparisonBenched()
            c.additional_renderers = self.additional_renderers
            c(self.__filename)

        def __print_name(self):
            cp = os.path.commonprefix([os.getcwd(), self.__filename])
            return self.__filename[len(cp) + 1:]

        def __str__(self):
            # zope.testrunner uses this to print
            return "%s (%s.%s)" % (self.__print_name(),
                                   self.__class__.__module__,
                                   self.__class__.__name__)

    for _, filename in testSuite():

        case = CompTestCase(filename)
        if filename.endswith('align.tex') and not has_binaries:
            # This one doesn't work right because it uses images
            case.additional_renderers = (('.txt', 'Text'),)
        suite.addTest(case)

    return suite
