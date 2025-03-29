"""Entry point for running the snippet runner as a module."""

import sys
from .snippet_runner.cli import main

if __name__ == "__main__":
    sys.exit(main())
