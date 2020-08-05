from typing import List


def append_if_all(iterable: List, *args) -> List:
    """Append args to a list if all args are true-like."""
    if all(args):
        for a in args:
            iterable.append(a)
    return iterable
