# Quicksort

## When to reach for it

- You need to sort an array in place with little extra memory.
- Average speed matters more than a guaranteed worst case, and stability doesn't matter.
- Variants: finding the k-th smallest item without sorting everything (quickselect), or sorting data with many duplicates using a three-way partition.

## The idea

Pick one item as the pivot. Rearrange the array so everything smaller than the pivot comes before it and everything larger comes after. That's the partition step, done in place with swaps in one pass. The pivot is now in its final position. Sort the left part and the right part the same way. There's no merge step, because once both sides are sorted, the whole array is.

The pivot choice decides the speed. A random pivot (or the median of three items) splits the array roughly in half on average, giving O(n log n). Always taking the first or last item can split off just one item at a time on sorted input, giving O(n²).

With many equal keys, a two-way partition keeps putting the duplicates on one side. A three-way partition keeps a middle group equal to the pivot and never recurses into it.

## Steps

1. If the range has fewer than two items, stop.
2. Choose a pivot, ideally at random, and partition the range around it.
3. Recurse on the part before the pivot and the part after it. Recursing on the smaller part first and looping on the larger keeps the stack at O(log n).
4. For quickselect, recurse only into the side that contains position k.

## Cost

O(n log n) average time, O(n²) worst case. O(log n) extra space for recursion on average. Not stable. Quickselect averages O(n).

## Common mistakes

- Always choosing the first or last item as the pivot, which is quadratic on already sorted input.
- Ignoring duplicates: with many equal keys, a two-way partition degrades toward O(n²).
- Calling it stable. Partition swaps can reorder equal items.
- Describing only "pick a pivot and split" without explaining how the split happens in place.
- Building new lists for each side, which gives up the in-place advantage.

## Easily confused with

- **Merge sort** splits by position, not by value, and does its work in the merge. It's stable with a guaranteed O(n log n), but needs O(n) extra space.
- **Three-way partitioning (Dutch national flag)** is quicksort's partition with a middle group for equal keys.
- **Heapsort** is also in place with a guaranteed O(n log n), but usually slower in practice.
