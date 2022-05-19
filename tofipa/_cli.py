import argparse
import sys

from . import (__description__, __project_name__, __version__, _config,
               _errors, _location)


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
        '--location', '-l',
        # TODO: Always use "extend" when Python 3.7 is no longer supported.
        #       https://docs.python.org/3/library/argparse.html#action
        action='extend' if sys.version_info >= (3, 8, 0) else 'append',
        nargs='+' if sys.version_info >= (3, 8, 0) else None,
        default=[],
        help=(
            'Potential download location of existing files in TORRENT '
            '(may be given multiple times)'
        ),
    )
    argparser.add_argument(
        '--locations-file', '--lf',
        default=_config.DEFAULT_LOCATIONS_FILEPATH,
        help='File containing newline-separated list of download locations',
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


def _fatal_error(msg):
    sys.stderr.write(f'{msg}\n')
    sys.exit(1)


def cli(args=None):
    if args is None:
        args = sys.argv[1:]
    args = _parse_args(args)

    # Debugging
    if args.debug_file:
        import logging
        logging.basicConfig(filename=args.debug_file, level=logging.DEBUG)

    # Read locations file
    try:
        locations = _config.Locations(filepath=args.locations_file)
    except _errors.ConfigError as e:
        _fatal_error(e)
    else:
        # Prepend arguments from --location to locations from config file
        locations[0:0] = args.location
        if not locations:
            _fatal_error(f'No locations specified. See: {__project_name__} --help')

    # Find location for torrent
    location_finder = _location.FindDownloadLocation(
        torrent=args.TORRENT,
        locations=locations,
        default=args.default,
    )
    try:
        download_location = location_finder.find()
    except _errors.FindError as e:
        sys.stderr.write(f'{e}\n')
    else:
        sys.stdout.write(f'{download_location}\n')
