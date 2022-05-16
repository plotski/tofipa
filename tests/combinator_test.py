import pytest

from tofipa._combinator import Combinator


@pytest.mark.parametrize(
    argnames='input, exp_output',
    argvalues=(
        ({'a': [], 'b': [], 'c': []}, []),
        ({'a': [], 'b': [], 'c': ['c1']}, []),
        ({'a': [], 'b': ['b1'], 'c': []}, []),
        ({'a': ['a1'], 'b': [], 'c': []}, []),
        ({'a': [], 'b': ['b1'], 'c': ['c1']}, []),
        ({'a': ['a1'], 'b': ['b1'], 'c': []}, []),
        ({'a': ['a1'], 'b': [], 'c': ['c1']}, []),
        ({'a': ['a1'], 'b': ['b1'], 'c': ['c1']}, [[('a', 'a1'), ('b', 'b1'), ('c', 'c1')]]),
        (
            {'a': ['a1', 'a2'], 'b': ['b1', 'b2'], 'c': ['c1', 'c2']},
            [
                [('a', 'a1'), ('b', 'b1'), ('c', 'c1')],
                [('a', 'a1'), ('b', 'b1'), ('c', 'c2')],
                [('a', 'a1'), ('b', 'b2'), ('c', 'c1')],
                [('a', 'a1'), ('b', 'b2'), ('c', 'c2')],
                [('a', 'a2'), ('b', 'b1'), ('c', 'c1')],
                [('a', 'a2'), ('b', 'b1'), ('c', 'c2')],
                [('a', 'a2'), ('b', 'b2'), ('c', 'c1')],
                [('a', 'a2'), ('b', 'b2'), ('c', 'c2')],
            ],
        ),
        (
            {'a': ['a1', 'a2', 'a3'], 'b': ['b1'], 'c': ['c1', 'c2']},
            [
                [('a', 'a1'), ('b', 'b1'), ('c', 'c1')],
                [('a', 'a1'), ('b', 'b1'), ('c', 'c2')],
                [('a', 'a2'), ('b', 'b1'), ('c', 'c1')],
                [('a', 'a2'), ('b', 'b1'), ('c', 'c2')],
                [('a', 'a3'), ('b', 'b1'), ('c', 'c1')],
                [('a', 'a3'), ('b', 'b1'), ('c', 'c2')],
            ],
        ),
        (
            {'a': ['a1'], 'b': ['b1', 'b2', 'b3'], 'c': ['c1', 'c2', 'c3']},
            [
                [('a', 'a1'), ('b', 'b1'), ('c', 'c1')],
                [('a', 'a1'), ('b', 'b1'), ('c', 'c2')],
                [('a', 'a1'), ('b', 'b1'), ('c', 'c3')],
                [('a', 'a1'), ('b', 'b2'), ('c', 'c1')],
                [('a', 'a1'), ('b', 'b2'), ('c', 'c2')],
                [('a', 'a1'), ('b', 'b2'), ('c', 'c3')],
                [('a', 'a1'), ('b', 'b3'), ('c', 'c1')],
                [('a', 'a1'), ('b', 'b3'), ('c', 'c2')],
                [('a', 'a1'), ('b', 'b3'), ('c', 'c3')],
            ],
        ),
    ),
)
def test_Combinator_iterates_over_all_combinations(input, exp_output):
    print('INPUT:', input)

    output = list(Combinator(input))

    print('OUTPUT:')
    for pairs in output:
        print('  ', pairs)
    print('EXPECTED OUTPUT:')
    for pairs in exp_output:
        print('  ', pairs)

    assert output == exp_output


@pytest.mark.parametrize(
    argnames='input, pre_iter_locks, mid_iter_locks, exp_output',
    argvalues=(
        (
            # input
            {'a': ['a1', 'a2', 'a3'], 'b': ['b1', 'b2', 'b3'], 'c': ['c1', 'c2', 'c3'], 'd': ['d1', 'd2', 'd3']},
            # pre_iter_locks
            [],
            # mid_iter_locks
            [
                {'on_pairs': (('a', 'a1'), ('b', 'b1'), ('c', 'c1'), ('d', 'd1')), 'locks': ('d',)},
                {'on_pairs': (('a', 'a1'), ('b', 'b1'), ('c', 'c2'), ('d', 'd1')), 'locks': ('c', 'b')},
                {'on_pairs': (('a', 'a3'), ('b', 'b1'), ('c', 'c2'), ('d', 'd1')), 'locks': ('a',)},
            ],
            # exp_output
            [
                [('a', 'a1'), ('b', 'b1'), ('c', 'c1'), ('d', 'd1')],
                [('a', 'a1'), ('b', 'b1'), ('c', 'c2'), ('d', 'd1')],
                [('a', 'a2'), ('b', 'b1'), ('c', 'c2'), ('d', 'd1')],
                [('a', 'a3'), ('b', 'b1'), ('c', 'c2'), ('d', 'd1')],
            ],
        ),
        (
            # input
            {'a': ['a1', 'a2', 'a3'], 'b': ['b1', 'b2', 'b3'], 'c': ['c1', 'c2', 'c3'], 'd': ['d1', 'd2', 'd3']},
            # pre_iter_locks
            ['b'],
            # mid_iter_locks
            [
                {'on_pairs': (('a', 'a1'), ('b', 'b1'), ('c', 'c1'), ('d', 'd3')), 'locks': ('d', 'a')},
            ],
            # exp_output
            [
                [('a', 'a1'), ('b', 'b1'), ('c', 'c1'), ('d', 'd1')],
                [('a', 'a1'), ('b', 'b1'), ('c', 'c1'), ('d', 'd2')],
                [('a', 'a1'), ('b', 'b1'), ('c', 'c1'), ('d', 'd3')],
                [('a', 'a1'), ('b', 'b1'), ('c', 'c2'), ('d', 'd3')],
                [('a', 'a1'), ('b', 'b1'), ('c', 'c3'), ('d', 'd3')],
            ],
        ),
        (
            # input
            {'a': ['a1', 'a2', 'a3'], 'b': ['b1', 'b2', 'b3'], 'c': ['c1', 'c2', 'c3'], 'd': ['d1', 'd2', 'd3']},
            # pre_iter_locks
            ['d', 'c'],
            # mid_iter_locks
            [
                {'on_pairs': (('a', 'a2'), ('b', 'b2'), ('c', 'c1'), ('d', 'd1')), 'locks': ('a',)},
            ],
            # exp_output
            [
                [('a', 'a1'), ('b', 'b1'), ('c', 'c1'), ('d', 'd1')],
                [('a', 'a1'), ('b', 'b2'), ('c', 'c1'), ('d', 'd1')],
                [('a', 'a1'), ('b', 'b3'), ('c', 'c1'), ('d', 'd1')],
                [('a', 'a2'), ('b', 'b1'), ('c', 'c1'), ('d', 'd1')],
                [('a', 'a2'), ('b', 'b2'), ('c', 'c1'), ('d', 'd1')],
                [('a', 'a2'), ('b', 'b3'), ('c', 'c1'), ('d', 'd1')],

            ],
        ),
    ),
)
def test_Combinator_does_not_change_locked_combinations(input, pre_iter_locks, mid_iter_locks, exp_output):
    print('INPUT:', input)

    combinator = Combinator(input)
    combinator.lock(*pre_iter_locks)
    mid_iter_locks = {tuple(lock['on_pairs']): lock['locks'] for lock in mid_iter_locks}
    output = []
    for pairs in combinator:
        output.append(pairs)

        locks = mid_iter_locks.get(tuple(pairs), ())
        if locks:
            combinator.lock(*locks)

    print('OUTPUT:')
    for pairs in output:
        print('  ', pairs)
    print('EXPECTED OUTPUT:')
    for pairs in exp_output:
        print('  ', pairs)

    assert output == exp_output


def test_Combinator_does_not_lock_unknown_key():
    combinator = Combinator({'a': ['a1'], 'b': ['b1'], 'c': ['c1']})
    with pytest.raises(RuntimeError, match=rf'Cannot exclude unknown key: {repr("bb")}'):
        combinator.lock('a', 'b', 'bb', 'c')
