# Prefix sums

## When to reach for it

- You get many questions of the form "what's the total from position i to position j?" over data that doesn't change.
- You need to count or find the contiguous stretches whose total is exactly some target, possibly with negative numbers.
- Variants: totals over rectangles in a grid, or applying many range updates and reading the result once (a difference array).

## The idea

Precompute `pre[i]`, the total of everything before position i, with `pre[0] = 0`. Then the total from i to j is `pre[j + 1] − pre[i]`: everything up to j minus everything before i. After one O(n) pass, every range question takes O(1).

To count stretches that hit a target, walk left to right keeping the total so far. A stretch ending here sums to the target exactly when some earlier total equals `current − target`. Keep a hash map from each total seen so far to how many times it's appeared, starting with `{0: 1}` for the empty prefix. At each position, add `count[current − target]` to the answer, then record the current total. This works with negative numbers, which break a sliding window.

## Steps

1. Build `pre` with one extra slot: `pre[0] = 0`, `pre[i + 1] = pre[i] + a[i]`.
2. Answer each range question as `pre[j + 1] − pre[i]`.
3. For target counts: `seen = {0: 1}`, `total = 0`. For each item, `total += item`, add `seen[total − target]` to the answer, then increment `seen[total]`.
4. For a grid, use `pre[r][c]`, the total of the rectangle above and left, and combine four corners per question.

## Cost

O(n) to build and O(1) per range question. The target count is O(n) time with O(n) space for the map. A grid is O(rows × cols) to build and O(1) per rectangle.

## Common mistakes

- Summing each range from scratch, which is O(n) per question.
- Off-by-one indexing: forgetting the extra 0 at the start, so ranges beginning at position 0 need a special case.
- Forgetting to seed the map with `{0: 1}`, which misses stretches that start at the beginning.
- Recording the current total before looking it up, which counts empty stretches when the target is 0.
- Using a sliding window when values can be negative.
- Using it when the data changes between questions. Each change forces a rebuild; a Fenwick tree handles updates.

## Easily confused with

- **Sliding window** finds best stretches with one pass, but only when growing and shrinking change the rule in one direction (for example, all values positive).
- **Dynamic programming** also stores running values, but each depends on a choice, not just a sum.
- **Hash-map lookups for pairs** (like "two numbers summing to a target") use the same trick, applied to single items instead of running totals.
