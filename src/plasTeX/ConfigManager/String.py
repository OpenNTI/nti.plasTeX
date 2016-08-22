#!/usr/bin/env python
from __future__ import absolute_import
from six import text_type
from six.moves import UserString
from .Generic import GenericOption, DEFAULTS, GenericParser, GenericArgument


class StringParser(GenericParser):
    pass


class StringOption(StringParser, GenericOption, UserString):

    """ String configuration option """

    synopsis = ''

    def __init__(self, docstring=DEFAULTS['docstring'],
                 options=DEFAULTS['options'],
                 default=DEFAULTS['default'],
                 optional=DEFAULTS['optional'],
                 values=DEFAULTS['values'],
                 category=DEFAULTS['category'],
                 callback=DEFAULTS['callback'],
                 synopsis=DEFAULTS['synopsis'],
                 environ=DEFAULTS['environ'],
                 registry=DEFAULTS['registry'],
                 mandatory=None,
                 name=DEFAULTS['name'],
                 source=DEFAULTS['source']):
        UserString.__init__(self, '')
        GenericOption.initialize(self, locals())

    def __getnewargs__(self):
        # Python 3.5 UserString added this and tries to
        # copy self.data by slicing it: self.data[:]. But
        # our data may actually be None (which is weird for a str,
        # but there you go) if we were just initialized with that as
        # a default (as for --config)
        return (self.data if not self.data else self.data[:],)

    def cast(self, arg):
        if arg is None:
            return
        return text_type(arg)

    def __iadd__(self, other):
        if callable(self.callback):
            other = self.callback(self.cast(other))

        if other is None:
            return self

        if self.data is None:
            self.data = self.cast(other)
        else:
            self.data += '\n%s' % self.cast(other)

        return self


class StringArgument(GenericArgument, StringOption):

    """ String command-line option """
