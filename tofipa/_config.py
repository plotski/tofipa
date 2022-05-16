import errno
import os
import re

from xdg.BaseDirectory import xdg_config_home

from . import __project_name__, _errors

DEFAULT_LOCATIONS_FILEPATH = os.path.join(xdg_config_home, __project_name__, 'locations')
DEFAULT_CLIENTS_FILEPATH = os.path.join(xdg_config_home, __project_name__, 'clients')


class LocationsFile(list):
    """
    :class:`list` subclass that reads directory paths from `filepath`

    Directory paths are separated by newlines. Lines that start with "#" are
    ignored.

    :raise ConfigError: if reading `filepath` fails or if it contains a file
        path
    """

    def __init__(self, filepath):
        self._filepath = filepath
        super().__init__(self._read(filepath))

    @property
    def filepath(self):
        return self._filepath

    def __repr__(self):
        return f'<{type(self).__name__} {self._filepath!r} {list(self)!r}>'

    def _read(self, filepath):
        locations = []

        try:
            with open(filepath, 'r') as f:
                for line_number, line in enumerate(f.readlines(), start=1):
                    line = line.strip()
                    if not line.startswith('#'):
                        locations.extend(self._parse_line(line, filepath, line_number))
        except OSError as e:
            # Ignore missing default config file path
            if e.errno == errno.ENOENT and filepath == DEFAULT_LOCATIONS_FILEPATH:
                pass
            else:
                msg = e.strerror if e.strerror else str(e)
                raise _errors.ConfigError(f'Failed to read {filepath}: {msg}')

        return locations

    def _parse_line(self, line, filepath, line_number):
        subdirs = []

        if line.endswith(f'{os.sep}*'):
            # Expand "*"
            parent_dir = line[:-2]
            try:
                subdir_names = os.listdir(parent_dir)
            except OSError as e:
                msg = e.strerror if e.strerror else str(e)
                raise _errors.ConfigError(f'Failed to read subdirectories from {parent_dir}: {msg}',
                                          filepath=filepath, line_number=line_number)
            else:
                for name in subdir_names:
                    subdir_path = os.path.join(parent_dir, name)
                    # Exclude non-directories (files and exotic stuff like
                    # sockets), but include nonexisting paths (subdir_path may
                    # contain unresolved environment variables and download
                    # locations may not exist anyway)
                    if os.path.isdir(subdir_path) or not os.path.exists(subdir_path):
                        subdirs.append(subdir_path)
        else:
            subdirs.append(line)

        # Resolve environment variables
        subdirs = [
            self._resolve_env_vars(subdir, filepath, line_number)
            for subdir in subdirs
        ]

        # Complain if subdir exists but is not a directory
        for subdir in subdirs:
            if os.path.exists(subdir) and not os.path.isdir(subdir):
                raise _errors.ConfigError(f'Not a directory: {subdir}',
                                          filepath=filepath, line_number=line_number)

        return sorted(subdirs)

    def _resolve_env_vars(self, string, filepath, line_number):
        # Resolve "~/foo" and "~user/foo"
        string = os.path.expanduser(string)

        while True:
            # Find valid variable name
            # https://stackoverflow.com/a/2821201
            match = re.search(r'\$([a-zA-Z_]+[a-zA-Z0-9_]*)', string)
            if not match:
                break
            else:
                env_var_name = match.group(1)
                env_var_value = os.environ.get(env_var_name, None)
                if env_var_value is None:
                    raise _errors.ConfigError(f'Unset environment variable: ${env_var_name}',
                                              filepath=filepath, line_number=line_number)
                elif env_var_value == '':
                    raise _errors.ConfigError(f'Empty environment variable: ${env_var_name}',
                                              filepath=filepath, line_number=line_number)
                else:
                    string = string.replace(f'${env_var_name}', env_var_value)

        return string
