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
