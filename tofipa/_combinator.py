import collections


class Combinator(collections.abc.Iterable):
    """
    Take a dictionary that maps keys to lists and turn it into a list of all
    possible ``(key, list item)`` combinations

    Example:

    >>> things = {
    >>>     'a': ['a1', 'a2'],
    >>>     'b': ['b1'],
    >>>     'c': ['c1', 'c2', 'c3', 'c4'],
    >>> }
    >>> list(_Combinator(things))
    >>> [
    >>>     [('a', 'a1'), ('b', 'b1'), ('c', 'c1')],
    >>>     [('a', 'a1'), ('b', 'b1'), ('c', 'c2')],
    >>>     [('a', 'a1'), ('b', 'b1'), ('c', 'c3')],
    >>>     [('a', 'a1'), ('b', 'b1'), ('c', 'c4')],
    >>>     [('a', 'a2'), ('b', 'b1'), ('c', 'c1')],
    >>>     [('a', 'a2'), ('b', 'b1'), ('c', 'c2')],
    >>>     [('a', 'a2'), ('b', 'b1'), ('c', 'c3')],
    >>>     [('a', 'a2'), ('b', 'b1'), ('c', 'c4')],
    >>> ]
    """

    def __init__(self, things):
        self._things = {
            key: tuple(items)
            for key, items in things.items()
        }
        self._keys = tuple(self._things)
        self._indexes = {
            key: 0 if len(self._things[key]) > 0 else -1
            for key in self._keys
        }
        self._locked_keys = set()

    @property
    def _current_pairs(self):
        # List of (key, list item) tuples for each key using current list
        # indexes.
        pairs = []
        for key in self._keys:
            item = self._things[key][self._indexes[key]]
            pairs.append((key, item))
        return pairs

    def __iter__(self):
        # Take the first step so the while loop below doesn't immediately end
        # because all indexes are zero.
        # Do not take the first step if any list is empty.
        if (
            all(index >= 0 for key, index in self._indexes.items())
            and any(key not in self._locked_keys for key in self._keys)
        ):
            yield self._current_pairs
            self._advance()

        # Yield over pairs until all keys are either at their start position 0
        # again or locked to a specific index. Don't loop at all if any list is
        # empty (indicated by index == -1, see __init__).
        while any(index > 0 and key not in self._locked_keys
                  for key, index in self._indexes.items()):
            yield self._current_pairs
            self._advance()

    def _advance(self):
        # Increase the rightmost index or reset it to zero and increase the next
        # index on the left.
        for key in reversed(self._keys):
            if key not in self._locked_keys:
                if self._indexes[key] < len(self._things[key]) - 1:
                    self._indexes[key] += 1
                    break
                else:
                    self._indexes[key] = 0
            else:
                continue

    def lock(self, *keys):
        """
        Do not change the current combination for every `key` in `keys`

        You should call this if you are happy with the current `key` ->
        `list_item` combination to prevent iterating over any other combinations
        for `key`. This can safe lots of iterations.

        :param keys`: Any key from the `things` mapping from initialization
        """
        for key in keys:
            if key not in self._keys:
                raise RuntimeError(f'Cannot exclude unknown key: {key!r}')
        self._locked_keys.update(keys)
