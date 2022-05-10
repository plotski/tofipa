__project_name__ = 'tofipa'
__description__ = 'Get download directory from torrent file'
__homepage__ = 'https://github.com/plotski/tofipa'
__version__ = '0.0.0'
__author__ = 'plotski'
__author_email__ = 'plotski@example.org'

from ._cli import cli
from ._errors import FindError
from ._location import FindDownloadLocation
