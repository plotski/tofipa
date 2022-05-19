import os

import pytest

from tofipa import _config, _errors


def test_LocationsFile_filepath(mocker):
    mocker.patch('tofipa._config.LocationsFile._read')

    locations = _config.LocationsFile('path/to/locations')

    assert locations.filepath == 'path/to/locations'


def test_LocationsFile_repr(mocker):
    mocker.patch('tofipa._config.LocationsFile._read', return_value=['/the/usual/path'])

    locations = _config.LocationsFile('path/to/locations')
    locations.extend(('/a/path', 'also/this/path'))

    assert repr(locations) == (
        "<LocationsFile"
        " 'path/to/locations'"
        " ['/the/usual/path', '/a/path', 'also/this/path']"
        ">"
    )


def test_LocationsFile_read_reads_filepath(tmp_path, mocker):
    mocker.patch('tofipa._config.LocationsFile._normalize',
                 side_effect=lambda line, fp, ln: (f'normalized {fp}@{ln}: {line}',))

    filepath = tmp_path / 'locations'
    filepath.write_text('''
    # A comment
    /path/one
    /path/two

       # Another comment
      path/t h r e e 
    '''.strip())  # noqa: W291 trailing whitespace
    locations = _config.LocationsFile(filepath)
    assert locations == [
        f'normalized {filepath}@2: /path/one',
        f'normalized {filepath}@3: /path/two',
        f'normalized {filepath}@6: path/t h r e e',
    ]


def test_LocationsFile_read_handles_nonexisting_default_file(mocker):
    mocker.patch('tofipa._config.LocationsFile._normalize', side_effect=lambda line, fp, ln: ('irrelevant',))
    mocker.patch('tofipa._config.DEFAULT_LOCATIONS_FILEPATH', 'mock/default/locations/file')
    filepath = _config.DEFAULT_LOCATIONS_FILEPATH
    locations = _config.LocationsFile(filepath)
    assert locations == []


def test_LocationsFile_read_handles_nonexisting_custom_file(mocker):
    mocker.patch('tofipa._config.LocationsFile._normalize', side_effect=lambda line, fp, ln: ('irrelevant',))
    filepath = 'mock/custom/locations/file'
    assert filepath != _config.DEFAULT_LOCATIONS_FILEPATH
    with pytest.raises(_errors.ConfigError, match=rf'^Failed to read {filepath}: No such file or directory$'):
        _config.LocationsFile(filepath)


def test_LocationsFile_normalize_expands_subdirectories(mocker, tmp_path):
    parent_directory = tmp_path / 'parent'
    parent_directory.mkdir()
    (parent_directory / 'subdir1').mkdir()
    (parent_directory / 'subdir2').mkdir()
    (parent_directory / 'subdir3').mkdir()
    (parent_directory / 'file1').write_text('foo')
    (parent_directory / 'file2').write_text('bar')

    mocker.patch('tofipa._config.LocationsFile._read')
    filepath = 'mock/locations/file'
    locations = _config.LocationsFile(filepath)

    return_value = locations._normalize(f'{parent_directory}{os.sep}*', filepath, 123)
    assert return_value == [
        str(parent_directory / 'subdir1'),
        str(parent_directory / 'subdir2'),
        str(parent_directory / 'subdir3'),
    ]


def test_LocationsFile_normalize_handles_exception_from_subdirectories_expansion(mocker, tmp_path):
    parent_directory = tmp_path / 'parent'
    parent_directory.mkdir()
    (parent_directory / 'subdir1').mkdir()
    (parent_directory / 'subdir2').mkdir()
    (parent_directory / 'subdir3').mkdir()
    (parent_directory / 'file1').write_text('foo')
    (parent_directory / 'file2').write_text('bar')
    parent_directory.chmod(0o000)

    mocker.patch('tofipa._config.LocationsFile._read')
    filepath = 'mock/locations/file'
    locations = _config.LocationsFile(filepath)

    try:
        with pytest.raises(_errors.ConfigError, match=(rf'{filepath}@123: Failed to read subdirectories '
                                                       rf'from {parent_directory}: Permission denied')):
            locations._normalize(f'{parent_directory}{os.sep}*', filepath, 123)
    finally:
        parent_directory.chmod(0o700)


@pytest.mark.parametrize('with_subdir_expansion', (True, False), ids=('with subdir expansion', 'without subdir expansion'))
def test_LocationsFile_normalize_resolves_environment_variables(with_subdir_expansion, mocker):
    mocker.patch('tofipa._config.LocationsFile._read')
    mocker.patch('tofipa._config.LocationsFile._resolve_env_vars',
                 side_effect=lambda string, fp, ln: f'resolved {fp}@{ln}: {string}')

    filepath = 'mock/locations/file'
    locations = _config.LocationsFile(filepath)

    if with_subdir_expansion:
        mocker.patch('os.listdir', return_value=('a', 'b', 'c'))
        return_value = locations._normalize(f'mock line{os.sep}*', filepath, 123)
        assert return_value == [
            f'resolved {filepath}@123: mock line{os.sep}a',
            f'resolved {filepath}@123: mock line{os.sep}b',
            f'resolved {filepath}@123: mock line{os.sep}c',
        ]
    else:
        return_value = locations._normalize('mock line', filepath, 123)
        assert return_value == [
            f'resolved {filepath}@123: mock line',
        ]


@pytest.mark.parametrize('with_subdir_expansion', (True, False), ids=('with subdir expansion', 'without subdir expansion'))
def test_LocationsFile_normalize_handles_subdir_being_file(with_subdir_expansion, mocker, tmp_path):
    mocker.patch('tofipa._config.LocationsFile._read')

    filepath = 'mock/locations/file'
    locations = _config.LocationsFile(filepath)

    if with_subdir_expansion:
        parent = tmp_path / 'parent'
        parent.mkdir()
        (parent / 'a').write_text('i am a file')
        (parent / 'b').write_text('i am b file')
        (parent / 'c').write_text('i am c file')
        return_value = locations._normalize(f'{parent}{os.sep}*', filepath, 123)
        assert return_value == []
    else:
        line = tmp_path / 'a file'
        line.write_text('i am a file')
        with pytest.raises(_errors.ConfigError, match=rf'^{filepath}@123: Not a directory: {line}$'):
            locations._normalize(str(line), filepath, 123)


def test_LocationsFile_resolve_env_vars_resolves_tilde(mocker):
    mocker.patch('tofipa._config.LocationsFile._read')
    mocker.patch('os.path.expanduser', return_value='path/with/expanded/tilde')

    filepath = 'mock/locations/file'
    locations = _config.LocationsFile(filepath)

    return_value = locations._resolve_env_vars('path/with/tilde', filepath, 123)
    assert return_value == 'path/with/expanded/tilde'


def test_LocationsFile_resolve_env_vars_resolves_environment_variables(mocker):
    mocker.patch('tofipa._config.LocationsFile._read')
    mocker.patch.dict('os.environ', {'FOO': 'The Foo', 'bar': 'The Bar'})

    filepath = 'mock/locations/file'
    locations = _config.LocationsFile(filepath)

    return_value = locations._resolve_env_vars('Foo/$FOO/foo/foo/$bar', filepath, 123)
    assert return_value == 'Foo/The Foo/foo/foo/The Bar'
    return_value = locations._resolve_env_vars('$bar/Bar/BAR/$FOO/bar/$bar', filepath, 123)
    assert return_value == 'The Bar/Bar/BAR/The Foo/bar/The Bar'


def test_LocationsFile_resolve_env_vars_handles_unset_environment_variable(mocker):
    mocker.patch('tofipa._config.LocationsFile._read')
    mocker.patch.dict('os.environ', {'FOO': 'The Foo', 'bar': 'The Bar'})

    filepath = 'mock/locations/file'
    locations = _config.LocationsFile(filepath)

    with pytest.raises(_errors.ConfigError, match=rf'^{filepath}@123: Unset environment variable: \$baz$'):
        locations._resolve_env_vars('Foo/$FOO/foo/foo/$bar/$baz', filepath, 123)


def test_LocationsFile_resolve_env_vars_handles_empty_environment_variable(mocker):
    mocker.patch('tofipa._config.LocationsFile._read')
    mocker.patch.dict('os.environ', {'FOO': 'The Foo', 'bar': 'The Bar', 'baz': ''})

    filepath = 'mock/locations/file'
    locations = _config.LocationsFile(filepath)

    with pytest.raises(_errors.ConfigError, match=rf'^{filepath}@123: Empty environment variable: \$baz$'):
        locations._resolve_env_vars('Foo/$FOO/foo/foo/$bar/$baz', filepath, 123)


def test_LocationsFile_normalizes_added_locations(mocker):
    mocker.patch('tofipa._config.LocationsFile._read', return_value=['initial/path'])
    mocker.patch('tofipa._config.LocationsFile._normalize',
                 side_effect=lambda l, f, n: (f'normalized:{l}:{f}:{n}',))

    filepath = 'mock/locations/file'
    locations = _config.LocationsFile(filepath)
    assert locations == ['initial/path']

    locations.append('appended/path')
    assert locations == ['initial/path', 'normalized:appended/path:None:None']

    locations.insert(1, 'inserted/path')
    assert locations == ['initial/path', 'normalized:inserted/path:None:None', 'normalized:appended/path:None:None']

    del locations[0]
    assert locations == ['normalized:inserted/path:None:None', 'normalized:appended/path:None:None']

    locations.extend(('some', 'more', 'paths'))
    assert locations == ['normalized:inserted/path:None:None', 'normalized:appended/path:None:None',
                         'normalized:some:None:None', 'normalized:more:None:None', 'normalized:paths:None:None']

    locations[1] = 'assigned/path'
    assert list(locations) == ['normalized:inserted/path:None:None', 'normalized:assigned/path:None:None',
                               'normalized:some:None:None', 'normalized:more:None:None', 'normalized:paths:None:None']

    locations[1:3] = ('multiple', 'assigned', 'paths')
    assert locations == ['normalized:inserted/path:None:None',
                         'normalized:multiple:None:None', 'normalized:assigned:None:None', 'normalized:paths:None:None',
                         'normalized:more:None:None', 'normalized:paths:None:None']
