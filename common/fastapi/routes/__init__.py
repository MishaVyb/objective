import sys

if sys.version_info < (3, 11):
    raise RuntimeError("Python>=3.11 required. ")

from . import monitoring
