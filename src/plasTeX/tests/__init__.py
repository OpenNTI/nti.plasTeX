import subprocess
from unittest import SkipTest

def _real_check_for_binaries():
    with open('/dev/null', 'wb') as f: # Unix specific (prior to Python 3)
        subprocess.check_call( ['kpsewhich', '--version'], stdout=f)

_check_for_binaries = _real_check_for_binaries

def _already_checked_for_binaries_and_failed():
    raise SkipTest("kpsewhich binary not found")

def _already_checked_for_binaries_and_worked():
    return

def skip_if_no_binaries():
    """
    If the TeX binaries are not available on the PATH in the simple
    way we use them in these tests, raise unittest's SkipTest
    exception. This supports testing on Travis CI.

    This is only a partial check and may be slow.
    """
    global _check_for_binaries
    try:
        _check_for_binaries()
        _check_for_binaries = _already_checked_for_binaries_and_worked
    except OSError:
        _check_for_binaries = _already_checked_for_binaries_and_failed
        _already_checked_for_binaries_and_failed()
