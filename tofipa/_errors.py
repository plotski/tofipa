class FindError(Exception):
    """Raised by :class:`~.FindDownloadLocation` and its methods"""


class ConfigError(Exception):
    """Raised by configuration file readers"""

    def __init__(self, msg, filepath=None, line_number=None):
        if filepath and line_number:
            super().__init__(f'{filepath}@{line_number}: {msg}')
        else:
            super().__init__(msg)
