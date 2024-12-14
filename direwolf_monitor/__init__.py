"""Top-level package for python-direwolf-monitor."""
from importlib.metadata import version, PackageNotFoundError

__author__ = """Walter A. Boring IV"""
__email__ = 'waboring@hemna.com'
try:
    __version__ = version("python_direwolf")
except PackageNotFoundError:
    # package is not installed
    pass

