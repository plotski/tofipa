import collections
import errno
import os
import re

from xdg.BaseDirectory import xdg_config_home

from . import __project_name__, _errors

DEFAULT_LOCATIONS_FILEPATH = os.path.join(xdg_config_home, __project_name__, 'locations')
DEFAULT_CLIENTS_FILEPATH = os.path.join(xdg_config_home, __project_name__, 'clients')


class Locations(collections.abc.MutableSequence):
    """
    :class:`list` subclass that reads directory paths from `filepath`

    Directory paths are separated by newlines. Lines that start with "#" are
    ignored.

    :raise ConfigError: if reading `filepath` fails or if it contains a file
        path
    """

    def __init__(self, *locations, filepath):
        self._filepath = filepath
        self._list = []
        # self.extend() should normalize `locations`. _read() does that on its
        # own and provides the proper filepath and line_number to ConfigError.
        self.extend(locations)
        self._list.extend(self._read(filepath))

    @property
    def filepath(self):
        return self._filepath

    def __repr__(self):
        return f'<{type(self).__name__} {self._filepath!r} {self._list!r}>'

    def _read(self, filepath):
        locations = []

        try:
            with open(filepath, 'r') as f:
                for line_number, line in enumerate(f.readlines(), start=1):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        locations.extend(self._normalize(line, filepath, line_number))
        except OSError as e:
            # Ignore missing default config file path
            if e.errno == errno.ENOENT and filepath == DEFAULT_LOCATIONS_FILEPATH:
                pass
            else:
                msg = e.strerror if e.strerror else str(e)
                raise _errors.ConfigError(f'Failed to read {filepath}: {msg}')

        return locations

    @classmethod
    def _normalize(cls, line, filepath, line_number):
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
            cls._resolve_env_vars(subdir, filepath, line_number)
            for subdir in subdirs
        ]

        # Complain if subdir exists but is not a directory
        for subdir in subdirs:
            if os.path.exists(subdir) and not os.path.isdir(subdir):
                raise _errors.ConfigError(f'Not a directory: {subdir}',
                                          filepath=filepath, line_number=line_number)

        return sorted(subdirs)

    @classmethod
    def _resolve_env_vars(cls, line, filepath, line_number):
        # Resolve "~/foo" and "~user/foo"
        path = os.path.expanduser(line)

        while True:
            # Find valid variable name
            # https://stackoverflow.com/a/2821201
            match = re.search(r'\$([a-zA-Z_]+[a-zA-Z0-9_]*)', path)
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
                    path = path.replace(f'${env_var_name}', env_var_value)

        return path

    def __setitem__(self, index, value):
        # `index` can be int or slice and `value` can be one path or list of
        # paths.
        if not isinstance(value, str) and isinstance(value, collections.abc.Iterable):
            normalized_paths = []
            for item in value:
                for normalized_path in self._normalize(item, None, None):
                    normalized_paths.append(normalized_path)
            self._list[index] = normalized_paths
        else:
            normalized_paths = self._normalize(value, None, None)
            self._list[index] = normalized_paths[0]

    def insert(self, index, value):
        # The only valid type for `index` should be int.
        normalized_paths = self._normalize(value, None, None)
        self._list.insert(index, normalized_paths[0])

    def __getitem__(self, index):
        return self._list[index]

    def __delitem__(self, index):
        del self._list[index]

    def __len__(self):
        return len(self._list)

    def __eq__(self, other):
        if isinstance(other, collections.abc.Sequence):
            return self._list == list(other)
        else:
            return NotImplemented
