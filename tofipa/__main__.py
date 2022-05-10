import sys

from ._cli import cli

sys.exit(cli(sys.argv[1:]))
