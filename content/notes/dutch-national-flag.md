# Dutch national flag

## When to reach for it

- Every item belongs to one of exactly three groups, and you need the groups next to each other.
- It has to happen in place, in one pass, with constant extra memory.
- The order inside each group doesn't matter. If it does, you need a stable method instead.

## The idea

Keep the array split into four regions with three indexes: `low`, `mid` and `high`.

- Everything before `low` is known to be group 1.
- Everything from `low` up to (not including) `mid` is known to be group 2.
- Everything after `high` is known to be group 3.
- Everything from `mid` to `high` is still unknown.

Look at the item at `mid` and move it to where it belongs. The unknown region shrinks by one every step, so the pass ends when `mid` passes `high`.

## Steps

1. Set `low = 0`, `mid = 0`, `high = n - 1`.
2. While `mid <= high`, look at the item at `mid`:
   - Group 1: swap it with the item at `low`, then move both `low` and `mid` forward.
   - Group 2: it's already in the right place; move `mid` forward.
   - Group 3: swap it with the item at `high` and move `high` back. Don't move `mid`, because the item that just arrived from `high` hasn't been looked at yet.

## Cost

O(n) time, since each step either moves `mid` forward or `high` back. O(1) extra space.

## Common mistakes

- Moving `mid` forward after swapping with `high`. The swapped-in item is unchecked and can end up in the wrong group.
- Stopping when `mid < high` instead of `mid <= high`, which leaves the last unknown item unchecked.
- Counting each group and then rewriting the array. That works for plain values, but it takes two passes and breaks when items carry other data that has to move with them.
- Claiming the result is stable. Swaps reorder items within a group.

## Easily confused with

- **Quicksort's partition step** splits into two groups around a pivot. Three-group partitioning is the variant that keeps a middle group equal to the pivot, which helps when there are many duplicates.
- **Sorting** solves it too, but in O(n log n) time. Three known groups need only one linear pass.
