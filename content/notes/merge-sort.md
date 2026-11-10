# Merge sort

## When to reach for it

- You need a guaranteed O(n log n) sort, or a stable one (equal items keep their original order).
- The data is too large for memory and has to be sorted in chunks on disk (external sorting).
- The data is a linked list or a stream that's read front to back.
- Variants: counting how many pairs are out of order while sorting.

## The idea

Split the list in half, sort each half the same way, then merge the two sorted halves. Merging is the core step: keep a pointer at the front of each half, repeatedly take the smaller front item and advance that pointer, and when one half runs out, copy the rest of the other. Taking from the left half on ties keeps the sort stable.

For data larger than memory, sort chunks that fit in memory and write each to disk as a sorted run. Then merge all the runs at once, reading each run front to back and using a small min-heap to find the smallest front item among them.

Counting out-of-order pairs fits the merge naturally: when an item from the right half is taken before items still waiting in the left half, it's out of order with every one of them, so add the number of items left in the left half.

## Steps

1. If the list has one item or none, it's sorted.
2. Split it into two halves and sort each recursively.
3. Merge: compare the fronts, take the smaller (the left one on ties), and repeat until both halves are used up.
4. External version: sort memory-sized chunks into runs, then do a k-way merge with a heap holding one front item per run.

## Cost

O(n log n) time in every case: log n levels of splitting, and O(n) merge work per level. O(n) extra space for merging arrays. External sorting reads and writes the data a small number of times, with memory for one chunk or one buffer per run.

## Common mistakes

- Describing only the split. The merge step is where the work happens and should be explained.
- Breaking ties toward the right half, which makes the sort unstable.
- Loading all the data into memory when the problem says it doesn't fit.
- Merging many runs by scanning all fronts every step instead of using a heap, which makes each step O(k) instead of O(log k).
- Counting out-of-order pairs with a nested loop, which is O(n²).

## Easily confused with

- **Quicksort** splits by value around a pivot and needs no merge. It's in place but not stable, and has a quadratic worst case.
- **Heaps** do the k-way merge in external sorting, but a heap alone isn't merge sort.
- **Divide and conquer** is the general strategy; merge sort is its best-known example.
