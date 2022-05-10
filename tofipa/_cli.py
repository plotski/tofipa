import argparse
import sys

from . import __description__, __project_name__, __version__
from ._errors import FindError
from ._location import FindDownloadLocation


def _parse_args(args):
    argparser = argparse.ArgumentParser(
        prog=__project_name__,
        description=__description__,
    )
    argparser.add_argument(
        'TORRENT',
        help='Path to torrent file',
    )
    argparser.add_argument(
        'LOCATION',
        nargs='+',
        help='Potential path of existing files in TORRENT',
    )
    argparser.add_argument(
        '--default',
        help='Default location if no existing files are found',
    )
    argparser.add_argument(
        '--version',
        action='version',
        version=f'{__project_name__} {__version__}',
    )
    argparser.add_argument(
        '--debug-file',
        help='Where to write debugging messages',
    )
    return argparser.parse_args(args)


def cli(args=None):
    if args is None:
        args = sys.argv[1:]
    args = _parse_args(args)

    if args.debug_file:
        import logging
        logging.basicConfig(filename=args.debug_file, level=logging.DEBUG)

    location_finder = FindDownloadLocation(
        torrent=args.TORRENT,
        locations=args.LOCATION,
        default=args.default,
    )
    try:
        download_location = location_finder.find()
    except FindError as e:
        sys.stderr.write(f'{e}\n')
    else:
        sys.stdout.write(download_location)
