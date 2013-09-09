#!/usr/bin/env python

"""
C.1.2 Environments (p167)

"""

from plasTeX import Command

logger = __import__('logging').getLogger(__name__)

class begin(Command):
	""" Beginning of an environment """
	args = 'name:str'

	def invoke(self, tex):
		""" Parse the \\begin{...} """
#		name = self.parse(tex)['name']
		name = tex.readArgument(type=str)
		logger.debug( 'Begin environment %s', name)

		self.ownerDocument.context.currenvir = name

		# Instantiate the correct macro and let it know
		# that it came from a \begin{...} macro
		obj = self.ownerDocument.createElement(name)
		obj.macroMode = Command.MODE_BEGIN
		obj.parentNode = self.parentNode

		# Return the output of the instantiated macro in
		# place of self
		out = obj.invoke(tex)
		if out is None:
			return [obj]
		return out

class end(Command):
	""" End of an environment """
	args = 'name:str'

	def invoke(self, tex):
		""" Parse the \\end{...} """
#		name = self.parse(tex)['name']
		name = tex.readArgument(type=str)
		logger.debug( 'End environment %s', name)

		# Instantiate the correct macro and let it know
		# that it came from a \end{...} macro
		obj = self.ownerDocument.createElement(name)
		obj.macroMode = Command.MODE_END
		obj.parentNode = self.parentNode

		# Return the output of the instantiated macro in
		# place of self
		out = obj.invoke(tex)
		if out is None:
			return [obj]

		while self.ownerDocument.context.currenvir is not None and \
			  not self.ownerDocument.context.currenvir == name:
			del self.ownerDocument.context.currenvir

		return out
