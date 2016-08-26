=========
 Changes
=========

1.0.0 (unreleased)
==================

- Better testing and code coverage.
- Remove broken and untested features:

  - Unix manpage renderer.
  - EPUB renderer.
  - CHM output from the XHTML renderer.
  - JavaHelp output from the XHTML renderer.
  - The deprecated ZPT alias for the PageTemplate renderer.
  - The S5 renderer.

- Enable the generation of an eclipse-toc.xml file by default from the
  XHTML renderer. This is not a true Eclipse help file anymore though.
  In addition to additions, such as embedded container support, it
  doesn't create the plugins 'eclipse-plugin' or 'eclipse-index' files.

- Use Chameleon with z3c.pt for rendering HTML and XML templates instead of an
  embedded copy of simpleTAL. This is faster, better documented,
  offers more flexible internationalization, is consistent with modern
  frameworks like Pyramid, is more customizable and powerful (it uses
  zope.traversing with in turn uses zope.component), and finally
  produces much better error messages.

  See `the chameleon referenece
  <http://chameleon.repoze.org/docs/latest/reference.html>`_ and the
  `TALES expression reference
  <http://docs.zope.org/zope2/zope2book/AppendixC.html#tales-path-expressions>`_.

  Support for using 'self' instead of 'here' in templates is
  preserved, but new templates should use 'here'.

  Unlike normal Chameleon/ZPT, for compatibility with simpleTAL, we
  default expressions to be non-escaped (substitution).

  Many users will want to set the ``CHAMELEON_CACHE`` environment
  directory appropriately.

- Remove the ``registerEngine`` method from the PageTemplate renderer.
  All engines should now be registered in the component registry.

- The Cheetah, genshi, and Kid template support has been removed. It
  can easily be added back by a different package thanks to the
  extensibility introduced by the component registry.
