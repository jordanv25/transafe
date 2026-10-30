"""Minimum edit distance (Unit II) - dynamic programming with backtrace.

`damerau` adds adjacent transposition (optimal string alignment), the most
common typo besides insert/delete/substitute.
"""
from __future__ import annotations


def distance(a: str, b: str, sub_cost: int = 1, transpose: bool = True, max_d: int | None = None) -> int:
    """Edit distance; returns max_d+1 early if the bound is exceeded."""
    la, lb = len(a), len(b)
    if max_d is not None and abs(la - lb) > max_d:
        return max_d + 1
    prev2 = None
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else sub_cost
            v = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if transpose and i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                v = min(v, prev2[j - 2] + 1)
            cur[j] = v
        if max_d is not None and min(cur) > max_d:
            return max_d + 1
        prev2, prev = prev, cur
    return prev[lb]


def align(a: str, b: str):
    """Return (distance, ops) where ops is a list of (op, a_char, b_char).
    op in {'match','sub','ins','del'} - classic Levenshtein backtrace."""
    la, lb = len(a), len(b)
    D = [[0] * (lb + 1) for _ in range(la + 1)]
    for i in range(la + 1):
        D[i][0] = i
    for j in range(lb + 1):
        D[0][j] = j
    for i in range(1, la + 1):
        for j in range(1, lb + 1):
            c = 0 if a[i - 1] == b[j - 1] else 1
            D[i][j] = min(D[i - 1][j] + 1, D[i][j - 1] + 1, D[i - 1][j - 1] + c)
    ops, i, j = [], la, lb
    while i > 0 or j > 0:
        if i > 0 and j > 0 and D[i][j] == D[i - 1][j - 1] + (0 if a[i - 1] == b[j - 1] else 1):
            ops.append(("match" if a[i - 1] == b[j - 1] else "sub", a[i - 1], b[j - 1]))
            i, j = i - 1, j - 1
        elif i > 0 and D[i][j] == D[i - 1][j] + 1:
            ops.append(("del", a[i - 1], ""))
            i -= 1
        else:
            ops.append(("ins", "", b[j - 1]))
            j -= 1
    ops.reverse()
    return D[la][lb], ops
