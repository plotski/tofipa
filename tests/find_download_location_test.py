import collections
import errno
import os
import random
import re
import string
from unittest.mock import Mock, PropertyMock, call

import pytest
import torf

from tofipa import FindError, __project_name__
from tofipa._location import FindDownloadLocation


class MockFile(str):
    def __new__(cls, filepath, size):
        self = super().__new__(cls, filepath)
        self.size = size
        return self


@pytest.mark.parametrize(
    argnames='torrent, exp_torrent_filepath',
    argvalues=(
        ('foo.torrent', 'foo.torrent'),
        (123, '123'),
    ),
)
def test_FindDownloadLocation_init_torrent_argument(torrent, exp_torrent_filepath):
    fdl = FindDownloadLocation(torrent=torrent, locations=('a', 'b', 'c'))
    assert fdl._torrent_filepath == exp_torrent_filepath

@pytest.mark.parametrize(
    argnames='locations, exp_exception, exp_locations',
    argvalues=(
        ((), RuntimeError('You must provide at least one potential download location'), ()),
        (['foo', 123], None, ('foo', '123')),
    ),
)
def test_FindDownloadLocation_init_locations_argument(locations, exp_exception, exp_locations):
    if exp_exception:
        with pytest.raises(type(exp_exception), match=rf'^{re.escape(str(exp_exception))}$'):
            FindDownloadLocation(torrent='mock.torrent', locations=locations)
    else:
        fdl = FindDownloadLocation(torrent='mock.torrent', locations=locations)
        assert fdl._locations == exp_locations

@pytest.mark.parametrize(
    argnames='default, exp_default_location',
    argvalues=(
        (None, None),
        ('', None),
        ('/foo/bar', '/foo/bar'),
        (123, '123'),
    ),
)
def test_FindDownloadLocation_init_default_argument(default, exp_default_location):
    fdl = FindDownloadLocation(torrent='mock.torrent', locations=('a', 'b', 'c'), default=default)
    assert fdl._default_location == exp_default_location


@pytest.mark.parametrize(
    argnames='locations, default, torf_error, location, exp_get_download_location_calls, exp_exception, exp_return_value',
    argvalues=(
        # Error reading torrent file
        (('a', 'b', 'c'), None, torf.TorfError('nope'), None, [], FindError('nope'), None),
        # Download location is found without default download location
        (('a', 'b', 'c',), None, None, 'download/path', [call()], None, 'download/path'),
        # Download location is found with default download location
        (('a', 'b', 'c',), 'default/path', None, 'download/path', [call()], None, 'download/path'),
        # Download location is not found with default download location
        (('a', 'b', 'c',), 'default/path', None, None, [call()], None, 'default/path'),
        # Download location is not found without default download location
        (('a', 'b', 'c',), None, None, None, [call()], None, 'a'),
    ),
)
def test_FindDownloadLocation_find(locations, default, torf_error, location,
                                   exp_get_download_location_calls, exp_exception, exp_return_value,
                                   mocker, tmp_path):
    fdl = FindDownloadLocation(
        torrent='mock.torrent',
        locations=locations,
        default=default,
    )
    mocker.patch.object(fdl, '_get_download_location', return_value=location)
    if torf_error:
        mocker.patch('torf.Torrent.read', side_effect=torf_error)
    else:
        mocker.patch('torf.Torrent.read', return_value='mock torrent object')

    if exp_exception:
        with pytest.raises(type(exp_exception), match=rf'^{re.escape(str(exp_exception))}$'):
            fdl.find()
        assert fdl._torrent is None
    else:
        return_value = fdl.find()
        assert return_value == exp_return_value
        assert fdl._get_download_location.call_args_list == exp_get_download_location_calls
        if torf_error:
            assert fdl._torrent is None
        else:
            assert fdl._torrent == 'mock torrent object'


@pytest.mark.parametrize(
    argnames='linked_candidates, exp_download_location, exp_verified_files, exp_create_hardlink_calls',
    argvalues=(
        # All matching files are found on the first try.
        (
            # linked_candidates
            [
                {
                    'foo/1': {'filepath': 'x/1', 'location': 'a'},
                    'bar/2': {'filepath': 'y/2', 'location': 'b'},
                    'baz/3': {'filepath': 'z/3', 'location': 'c'},
                },
                {'ignored': {}},  # This should never be used
            ],
            # exp_download_location
            'a',
            # exp_verifed_files
            ['foo/1', 'bar/2', 'baz/3'],
            # exp_create_hardlink_calls
            [call('x/1', 'a/foo/1'), call('y/2', 'a/bar/2'), call('z/3', 'a/baz/3')],
        ),
        # Found one corrupt file. The second size match is used. The location of
        # the first content match is used.
        (
            # linked_candidates
            [
                {
                    'foo/1': {'filepath': 'FOO/one.corrupt', 'location': 'a'},
                    'bar/2': {'filepath': 'Foo/two', 'location': 'b'},
                    'baz/3': {'filepath': 'asdf/three', 'location': 'c'},
                },
                {
                    'foo/1': {'filepath': 'Foo/one', 'location': 'a'},
                    'bar/2': {'filepath': 'f00/two', 'location': 'b'},
                    'baz/3': {'filepath': 'FOO/three', 'location': 'c'},
                },
                {'ignored': {}},  # This should never be used
            ],
            # exp_download_location
            'b',
            # exp_verifed_files
            ['foo/1', 'bar/2', 'baz/3', 'foo/1'],
            # exp_create_hardlink_calls
            [call('Foo/one', 'b/foo/1'), call('Foo/two', 'b/bar/2'), call('asdf/three', 'b/baz/3')],
        ),
        # Not all wanted files have a match. List of candidates is exhausted.
        (
            # linked_candidates
            [
                {
                    'foo/1': {'filepath': 'FOO/one.corrupt', 'location': 'a'},
                    'bar/2': {'filepath': 'Foo/two.corrupt', 'location': 'b'},
                    'baz/3': {'filepath': 'asdf/three', 'location': 'c'},
                },
                {
                    'bar/2': {'filepath': 'f00/two.also.corrupt', 'location': 'b'},
                    'baz/3': {'filepath': 'FOO/three', 'location': 'c'},
                },
                {
                    'bar/2': {'filepath': 'foohoo/TWO', 'location': 'b'},
                },
            ],
            # exp_download_location
            'c',
            # exp_verifed_files
            ['foo/1', 'bar/2', 'baz/3', 'bar/2', 'bar/2'],
            # exp_create_hardlink_calls
            [call('foohoo/TWO', 'c/bar/2'), call('asdf/three', 'c/baz/3')],
        ),
    ),
)
def test_FindDownloadLocation_get_download_location(linked_candidates, exp_download_location,
                                                    exp_verified_files, exp_create_hardlink_calls,
                                                    mocker):
    tempdir_name = (
        'tempdir_'
        + ''.join(random.choice(string.ascii_letters) for _ in range(10))
    )
    corruptions = collections.defaultdict(lambda: [])
    for paths in linked_candidates:
        print('Set of candidates:')
        for file, cand in paths.items():
            if file != 'ignored':
                cand['temporary_location'] = tempdir_name
                corruptions[file].append('corrupt' if 'corrupt' in cand.get('filepath', '') else 'good')
                print('  ', file, cand)

    print('corruptions:', dict(corruptions))

    fdl = FindDownloadLocation(torrent='mock.torrent', locations=('a', 'b', 'c'))
    mocker.patch.object(fdl, '_torrent', Mock(files=tuple(linked_candidates[0])))
    mocker.patch.object(fdl, '_get_size_matching_candidates', return_value='mock size matches')
    mocker.patch.object(fdl, '_each_set_of_linked_candidates', return_value=linked_candidates)
    mocker.patch.object(fdl, '_create_hardlink')

    def verify_file_mock(file, location):
        corrupt = corruptions[file].pop(0)
        print('verifying', file, location, corrupt)
        return corrupt == 'good'

    mocker.patch.object(fdl, '_verify_file', side_effect=verify_file_mock)

    return_value = fdl._get_download_location()
    assert return_value == exp_download_location

    assert fdl._get_size_matching_candidates.call_args_list == [call()]
    assert fdl._each_set_of_linked_candidates.call_args_list == [call(fdl._get_size_matching_candidates.return_value)]
    assert fdl._verify_file.call_args_list == [
        call(file, location=tempdir_name)
        for file in exp_verified_files
    ]
    print(' links created:', sorted(fdl._create_hardlink.call_args_list))
    print('links expected:', sorted(exp_create_hardlink_calls))
    assert sorted(fdl._create_hardlink.call_args_list) == sorted(exp_create_hardlink_calls)


def test_FindDownloadLocation_each_set_of_linked_candidates(mocker, tmp_path):
    fdl = FindDownloadLocation(torrent='mock.torrent', locations=('a', 'b', 'c'))
    tempdir = str(tmp_path / 'templinks')
    mocker.patch.object(fdl, '_create_symlink')
    mocker.patch.object(type(fdl), '_temporary_directory', PropertyMock(return_value=Mock(
        __enter__=Mock(return_value=str(tempdir)),
        __exit__=Mock(),
    )))

    candidates = {
        'a': [{'filepath': 'a1'}],
        'b': [{'filepath': 'b1'}, {'filepath': 'b2'}],
        'c': [{'filepath': 'c1'}, {'filepath': 'c2'}, {'filepath': 'c3'}],
    }
    exp = [
        (
            # Linked files
            {'a': {'filepath': 'a1'}, 'b': {'filepath': 'b1'}, 'c': {'filepath': 'c1'}},
            # fdl._create_symlink() calls
            [
                call(os.path.abspath('a1'), os.path.join(tempdir, 'a')),
                call(os.path.abspath('b1'), os.path.join(tempdir, 'b')),
                call(os.path.abspath('c1'), os.path.join(tempdir, 'c')),
            ],
        ),
        (
            # Linked files
            {'a': {'filepath': 'a1'}, 'b': {'filepath': 'b1'}, 'c': {'filepath': 'c2'}},
            # fdl._create_symlink() calls
            [
                call(os.path.abspath('a1'), os.path.join(tempdir, 'a')),
                call(os.path.abspath('b1'), os.path.join(tempdir, 'b')),
                call(os.path.abspath('c2'), os.path.join(tempdir, 'c')),
            ],
        ),
        (
            # Linked files
            {'a': {'filepath': 'a1'}, 'b': {'filepath': 'b1'}, 'c': {'filepath': 'c3'}},
            # fdl._create_symlink() calls
            [
                call(os.path.abspath('a1'), os.path.join(tempdir, 'a')),
                call(os.path.abspath('b1'), os.path.join(tempdir, 'b')),
                call(os.path.abspath('c3'), os.path.join(tempdir, 'c')),
            ],
        ),
        (
            # Linked files
            {'a': {'filepath': 'a1'}, 'b': {'filepath': 'b2'}, 'c': {'filepath': 'c1'}},
            # fdl._create_symlink() calls
            [
                call(os.path.abspath('a1'), os.path.join(tempdir, 'a')),
                call(os.path.abspath('b2'), os.path.join(tempdir, 'b')),
                call(os.path.abspath('c1'), os.path.join(tempdir, 'c')),
            ],
        ),
        (
            # Linked files
            {'a': {'filepath': 'a1'}, 'b': {'filepath': 'b2'}, 'c': {'filepath': 'c2'}},
            # fdl._create_symlink() calls
            [
                call(os.path.abspath('a1'), os.path.join(tempdir, 'a')),
                call(os.path.abspath('b2'), os.path.join(tempdir, 'b')),
                call(os.path.abspath('c2'), os.path.join(tempdir, 'c')),
            ],
        ),
        (
            # Linked files
            {'a': {'filepath': 'a1'}, 'b': {'filepath': 'b2'}, 'c': {'filepath': 'c3'}},
            # fdl._create_symlink() calls
            [
                call(os.path.abspath('a1'), os.path.join(tempdir, 'a')),
                call(os.path.abspath('b2'), os.path.join(tempdir, 'b')),
                call(os.path.abspath('c3'), os.path.join(tempdir, 'c')),
            ],
        ),
    ]

    for paths in fdl._each_set_of_linked_candidates(candidates):
        exp_paths, create_symlink_calls = exp.pop(0)
        for candidate in exp_paths.values():
            candidate['temporary_location'] = tempdir
        assert paths == exp_paths
        assert fdl._create_symlink.call_args_list == create_symlink_calls
        fdl._create_symlink.reset_mock()

    # Assert _each_set_of_linked_candidates() went through all expected states
    assert len(exp) == 0


@pytest.mark.parametrize(
    argnames='piece_indexes, verify_piece_return_values, exp_verify_piece_calls, exp_return_value',
    argvalues=(
        ([1, 5, 11], [True, True, True], [call(1), call(5), call(11)], True),

        ([1, 5, 11], [True, True, False], [call(1), call(5), call(11)], False),
        ([1, 5, 11], [True, False, True], [call(1), call(5)], False),
        ([1, 5, 11], [False, True, True], [call(1)], False),

        ([1, 5, 11], [True, True, None], [call(1), call(5), call(11)], None),
        ([1, 5, 11], [True, None, True], [call(1), call(5)], None),
        ([1, 5, 11], [None, True, True], [call(1)], None),
    ),
)
def test_FindDownloadLocation_verify_file(piece_indexes, verify_piece_return_values, exp_verify_piece_calls,
                                          exp_return_value, mocker, tmp_path):
    fdl = FindDownloadLocation(torrent='mock.torrent', locations=('a', 'b', 'c'))
    mocker.patch.object(fdl, '_torrent')
    TorrentFileStream_mock = mocker.patch('torf.TorrentFileStream')
    tfs_mock = TorrentFileStream_mock.return_value.__enter__.return_value
    tfs_mock.get_absolute_piece_indexes.return_value = piece_indexes
    tfs_mock.verify_piece.side_effect = verify_piece_return_values
    mock_location = 'path/to/location'

    assert fdl._verify_file('mock/file/path', mock_location) is exp_return_value

    exp_content_path = os.path.join(mock_location, fdl._torrent.name)
    assert TorrentFileStream_mock.call_args_list == [call(fdl._torrent, content_path=exp_content_path)]
    assert tfs_mock.get_absolute_piece_indexes.call_args_list == [call('mock/file/path', (1, -2))]
    assert tfs_mock.verify_piece.call_args_list == exp_verify_piece_calls


def test_FindDownloadLocation_get_size_matching_candidates(mocker, tmp_path):
    files = (
        tmp_path / '.1',
        tmp_path / '.2',
        tmp_path / '.3',
        tmp_path / '.4',
        tmp_path / 'a' / 'a1',
        tmp_path / 'a' / 'a2',
        tmp_path / 'a' / 'a3',
        tmp_path / 'a' / 'a4',
        tmp_path / 'a' / 'b' / 'ab1',
        tmp_path / 'a' / 'b' / 'ab2',
        tmp_path / 'a' / 'b' / 'ab4',
        tmp_path / 'c' / 'c1',
        tmp_path / 'c' / 'c2',
        tmp_path / 'c' / 'c3',
        tmp_path / 'c' / 'c4',
    )
    for f in files:
        f.parent.mkdir(parents=True, exist_ok=True)
        filesize = int(f.name[-1])
        f.write_bytes(b'x' * filesize)

    fdl = FindDownloadLocation(
        torrent='mock.torrent',
        locations=(
            tmp_path / 'a',
            tmp_path / 'c',
        ),
    )
    mocker.patch.object(fdl, '_torrent', Mock(files=(
        # Same path
        MockFile('a/a1', size=1),
        # Same path, different file name
        MockFile('a/b/ab.2', size=2),
        # Different path, different file name
        MockFile('c/x/c3', size=3),
        # No matches
        MockFile('foo/bar0', size=0),
        MockFile('foo/baz5', size=5),
    )))

    exp_candidates = {
        str('a/a1'): [
            {'location': str(tmp_path / 'a'), 'filepath': str(tmp_path / 'a/a1'),
             'filepath_rel': 'a1', 'similarity': 0.6666666666666666},
            {'location': str(tmp_path / 'a'), 'filepath': str(tmp_path / 'a/b/ab1'),
             'filepath_rel': 'b/ab1', 'similarity': 0.4444444444444444},
            {'location': str(tmp_path / 'c'), 'filepath': str(tmp_path / 'c/c1'),
             'filepath_rel': 'c1', 'similarity': 0.3333333333333333},
        ],
        str('a/b/ab.2'): [
            {'location': str(tmp_path / 'a'), 'filepath': str(tmp_path / 'a/b/ab2'),
             'filepath_rel': 'b/ab2', 'similarity': 0.7692307692307693},
            {'location': str(tmp_path / 'a'), 'filepath': str(tmp_path / 'a/a2'),
             'filepath_rel': 'a2', 'similarity': 0.4},
            {'location': str(tmp_path / 'c'), 'filepath': str(tmp_path / 'c/c2'),
             'filepath_rel': 'c2', 'similarity': 0.2},
        ],
        str('c/x/c3'): [
            {'location': str(tmp_path / 'c'), 'filepath': str(tmp_path / 'c/c3'),
             'filepath_rel': 'c3', 'similarity': 0.5},
            {'location': str(tmp_path / 'a'), 'filepath': str(tmp_path / 'a/a3'),
             'filepath_rel': 'a3', 'similarity': 0.25},
        ],
    }
    candidates = fdl._get_size_matching_candidates()

    for file, cands in candidates.items():
        print(file)
        for c in cands:
            print('  ', c)
    print('--------------')
    for file, cands in exp_candidates.items():
        print(file)
        for c in cands:
            print('  ', c)

    assert candidates == exp_candidates


def test_FindDownloadLocation_each_file(tmp_path):
    files = (
        tmp_path / '1',
        tmp_path / 'a' / '2',
        tmp_path / 'a' / '3',
        tmp_path / 'a' / 'b' / '4',
        tmp_path / 'a' / 'b' / '5',
        tmp_path / 'a' / 'b' / '6',
        tmp_path / 'c' / '7',
        tmp_path / 'c' / '8',
    )
    for f in files:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b'mock data')

    fdl = FindDownloadLocation(torrent='mock.torrent', locations=('a', 'b', 'c'))
    assert sorted(fdl._each_file(tmp_path / 'a')) == [
        (str(tmp_path / 'a' / '2'), str(tmp_path / 'a')),
        (str(tmp_path / 'a' / '3'), str(tmp_path / 'a')),
        (str(tmp_path / 'a' / 'b' / '4'), str(tmp_path / 'a')),
        (str(tmp_path / 'a' / 'b' / '5'), str(tmp_path / 'a')),
        (str(tmp_path / 'a' / 'b' / '6'), str(tmp_path / 'a')),
    ]
    assert sorted(fdl._each_file(tmp_path / 'a', tmp_path / 'c' / '8')) == [
        (str(tmp_path / 'a' / '2'), str(tmp_path / 'a')),
        (str(tmp_path / 'a' / '3'), str(tmp_path / 'a')),
        (str(tmp_path / 'a' / 'b' / '4'), str(tmp_path / 'a')),
        (str(tmp_path / 'a' / 'b' / '5'), str(tmp_path / 'a')),
        (str(tmp_path / 'a' / 'b' / '6'), str(tmp_path / 'a')),
        (str(tmp_path / 'c' / '8'), str(tmp_path / 'c' / '8')),
    ]
    assert sorted(fdl._each_file(tmp_path / 'a', tmp_path / 'c')) == [
        (str(tmp_path / 'a' / '2'), str(tmp_path / 'a')),
        (str(tmp_path / 'a' / '3'), str(tmp_path / 'a')),
        (str(tmp_path / 'a' / 'b' / '4'), str(tmp_path / 'a')),
        (str(tmp_path / 'a' / 'b' / '5'), str(tmp_path / 'a')),
        (str(tmp_path / 'a' / 'b' / '6'), str(tmp_path / 'a')),
        (str(tmp_path / 'c' / '7'), str(tmp_path / 'c')),
        (str(tmp_path / 'c' / '8'), str(tmp_path / 'c')),
    ]
    assert sorted(fdl._each_file(tmp_path / 'a' / 'b', tmp_path / 'c')) == [
        (str(tmp_path / 'a' / 'b' / '4'), str(tmp_path / 'a' / 'b')),
        (str(tmp_path / 'a' / 'b' / '5'), str(tmp_path / 'a' / 'b')),
        (str(tmp_path / 'a' / 'b' / '6'), str(tmp_path / 'a' / 'b')),
        (str(tmp_path / 'c' / '7'), str(tmp_path / 'c')),
        (str(tmp_path / 'c' / '8'), str(tmp_path / 'c')),
    ]


def test_FindDownloadLocation_is_size_match(mocker):
    fdl = FindDownloadLocation(torrent='mock.torrent', locations=('a', 'b', 'c'))
    get_file_size_mock = mocker.patch.object(fdl, '_get_file_size', return_value=456)
    assert fdl._is_size_match(Mock(size=123), 'path/to/foo') is False
    assert get_file_size_mock.call_args_list == [call('path/to/foo')]
    assert fdl._is_size_match(Mock(size=456), 'path/to/bar') is True
    assert get_file_size_mock.call_args_list == [call('path/to/foo'), call('path/to/bar')]
    assert fdl._is_size_match(Mock(size=789), 'path/to/baz') is False
    assert get_file_size_mock.call_args_list == [call('path/to/foo'), call('path/to/bar'), call('path/to/baz')]


@pytest.mark.parametrize(
    argnames='is_dir, getsize_result, exp_return_value',
    argvalues=(
        (True, None, None),
        (True, OSError('nope'), None),
        (False, OSError('nope'), None),
        (False, 123456, 123456),
    ),
)
def test_FindDownloadLocation_get_file_size(is_dir, getsize_result, exp_return_value, mocker):
    fdl = FindDownloadLocation(torrent='mock.torrent', locations=('a', 'b', 'c'))
    isdir_mock = mocker.patch('os.path.isdir', return_value=is_dir)
    if isinstance(getsize_result, BaseException):
        getsize_mock = mocker.patch('os.path.getsize', side_effect=getsize_result)
    else:
        getsize_mock = mocker.patch('os.path.getsize', return_value=getsize_result)
    assert fdl._get_file_size('path/to/foo') is exp_return_value
    assert isdir_mock.call_args_list == [call('path/to/foo')]
    if is_dir:
        assert getsize_mock.call_args_list == []
    else:
        assert getsize_mock.call_args_list == [call('path/to/foo')]


def test_FindDownloadLocation_create_hardlink(mocker):
    fdl = FindDownloadLocation(torrent='mock.torrent', locations=('a', 'b', 'c'))
    mocker.patch.object(fdl, '_create_link', Mock(return_value='foo'))
    assert fdl._create_hardlink('path/to/source', 'path/to/target') == 'foo'
    assert fdl._create_link.call_args_list == [
        call(fdl._hardlink_or_symlink, 'path/to/source', 'path/to/target'),
    ]


@pytest.mark.parametrize(
    argnames='hardlink_exception, symlink_exception, exp_exception',
    argvalues=(
        (None, None, None),
        (None, OSError(errno.EACCES, 'Permission'), None),
        (OSError(errno.EACCES, 'Permission'), None, OSError(errno.EACCES, 'Permission')),
        (OSError(errno.EXDEV, 'Cross-device'), None, None),
        (OSError(errno.EXDEV, 'Cross-device'), OSError(errno.EACCES, 'Permission'), OSError(errno.EACCES, 'Permission')),
    ),
)
def test_FindDownloadLocation_hardlink_or_symlink(hardlink_exception, symlink_exception, exp_exception, mocker):
    fdl = FindDownloadLocation(torrent='mock.torrent', locations=('a', 'b', 'c'))
    hardlink_mock = mocker.patch('os.link', Mock(side_effect=hardlink_exception))
    symlink_mock = mocker.patch('os.symlink', Mock(side_effect=symlink_exception))
    if exp_exception:
        with pytest.raises(type(exp_exception), match=rf'^{re.escape(str(exp_exception))}$'):
            fdl._hardlink_or_symlink('path/to/source', 'path/to/target')
    else:
        assert fdl._hardlink_or_symlink('path/to/source', 'path/to/target') is None

    assert hardlink_mock.call_args_list == [call('path/to/source', 'path/to/target')]
    if hardlink_exception and hardlink_exception.errno == errno.EXDEV:
        assert symlink_mock.call_args_list == [call('path/to/source', 'path/to/target')]
    else:
        assert symlink_mock.call_args_list == []


def test_FindDownloadLocation_create_symlink(mocker):
    fdl = FindDownloadLocation(torrent='mock.torrent', locations=('a', 'b', 'c'))
    mocker.patch.object(fdl, '_create_link', Mock(return_value='foo'))
    assert fdl._create_symlink('path/to/source', 'path/to/target') == 'foo'
    assert fdl._create_link.call_args_list == [call(os.symlink, 'path/to/source', 'path/to/target')]


def test_FindDownloadLocation_create_link_that_already_exists(mocker):
    mocks = Mock()
    mocks.attach_mock(mocker.patch('os.path.exists', return_value=True), 'exists')
    mocks.attach_mock(mocker.patch('os.makedirs'), 'makedirs')
    mocks.attach_mock(Mock(__qualname__='mylink'), 'create_link_function')

    fdl = FindDownloadLocation(torrent='mock.torrent', locations=('a', 'b', 'c'))
    fdl._create_link(mocks.create_link_function, 'path/to/source', 'path/to/target')

    assert mocks.mock_calls == [
        call.exists('path/to/target'),
    ]

def test_FindDownloadLocation_create_link_fails_to_create_parent_directories(mocker):
    mocks = Mock()
    mocks.attach_mock(mocker.patch('os.path.exists', return_value=False), 'exists')
    mocks.attach_mock(mocker.patch('os.makedirs', side_effect=OSError('nope')), 'makedirs')
    mocks.attach_mock(Mock(__qualname__='mylink'), 'create_link_function')

    fdl = FindDownloadLocation(torrent='mock.torrent', locations=('a', 'b', 'c'))
    with pytest.raises(FindError, match=r'^Failed to create directory path/to: nope$'):
        fdl._create_link(mocks.create_link_function, 'path/to/source', 'path/to/target')

    assert mocks.mock_calls == [
        call.exists('path/to/target'),
        call.makedirs('path/to', exist_ok=True),
    ]

def test_FindDownloadLocation_create_link_fails_to_create_link(mocker):
    mocks = Mock()
    mocks.attach_mock(mocker.patch('os.path.exists', return_value=False), 'exists')
    mocks.attach_mock(mocker.patch('os.makedirs'), 'makedirs')
    mocks.attach_mock(Mock(__qualname__='mylink', side_effect=OSError('nope')), 'create_link_function')

    fdl = FindDownloadLocation(torrent='mock.torrent', locations=('a', 'b', 'c'))
    with pytest.raises(FindError, match=r'^Failed to link path/to/source to path/to/target: nope$'):
        fdl._create_link(mocks.create_link_function, 'path/to/source', 'path/to/target')

    assert mocks.mock_calls == [
        call.exists('path/to/target'),
        call.makedirs('path/to', exist_ok=True),
        call.create_link_function('path/to/source', 'path/to/target'),
    ]

def test_FindDownloadLocation_create_link_creates_link(mocker):
    mocks = Mock()
    mocks.attach_mock(mocker.patch('os.path.exists', return_value=False), 'exists')
    mocks.attach_mock(mocker.patch('os.makedirs'), 'makedirs')
    mocks.attach_mock(Mock(__qualname__='mylink'), 'create_link_function')

    fdl = FindDownloadLocation(torrent='mock.torrent', locations=('a', 'b', 'c'))
    fdl._create_link(mocks.create_link_function, 'path/to/source', 'path/to/target')

    assert mocks.mock_calls == [
        call.exists('path/to/target'),
        call.makedirs('path/to', exist_ok=True),
        call.create_link_function('path/to/source', 'path/to/target'),
    ]


def test_FindDownloadLocation_temporary_directory(mocker):
    fdl = FindDownloadLocation(torrent='mock.torrent', locations=('a', 'b', 'c'))
    fdl._torrent = Mock()
    fdl._torrent.name = f"This {os.sep} & That's It 1234"
    TemporaryDirectory_mock = mocker.patch('tempfile.TemporaryDirectory')
    assert fdl._temporary_directory is TemporaryDirectory_mock.return_value
    assert TemporaryDirectory_mock.call_args_list == [
        call(prefix=f"{__project_name__}.This _ _ That's It 1234."),
    ]
