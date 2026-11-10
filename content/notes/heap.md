# Heap

## When to reach for it

- You repeatedly need the smallest (or largest) item of a collection that keeps changing.
- You need the top k items from a large collection or a stream, without sorting all of it.
- You need a running median as numbers arrive.
- You need to merge many sorted lists, or always process the most urgent item next.

## The idea

A heap is a tree stored in an array where every parent is no larger than its children (a min-heap) or no smaller (a max-heap). The smallest item is always at the top, in O(1). Adding or removing an item takes O(log n), because only one path from the top to the bottom needs fixing.

**Top k of a stream:** keep a min-heap of size k holding the k largest items so far. Its top is the smallest of them, the one that would be dropped next. For each new item, if it beats the top, replace the top. Memory stays at O(k) however long the stream is. It's a min-heap even though you want the largest items, because what you need to see quickly is the weakest member.

**Running median:** keep the smaller half of the numbers in a max-heap and the larger half in a min-heap. Keep their sizes equal or within one. The median is the top of the bigger heap, or the average of both tops.

## Steps

1. Decide what has to be found quickly, the smallest or the largest, and choose a min- or max-heap.
2. For top k: push items until the heap holds k. After that, if a new item beats the top, pop the top and push the new item.
3. For the median: push each number onto one heap, move the top across if the halves are out of order, then rebalance the sizes.
4. When items have counts that change over time, finish counting first (with a hash map) and then run the heap over the final counts.

## Cost

O(log n) per insert or remove, O(1) to see the top. Top k of n items: O(n log k) time and O(k) space. Running median: O(log n) per new number.

## Common mistakes

- Using a max-heap of everything for top k, which needs O(n) memory and doesn't scale to streams.
- Sorting all n items, which is O(n log n) and needs all of them in memory.
- Pushing items whose keys keep changing while they're in the heap. The heap doesn't reorder itself, so stored keys go stale.
- Not saying the heap's size or why its top is the right item to compare against.
- Scanning a sorted list on every insert for the median, which is O(n) per number.

## Easily confused with

- **Sorting** finds the top k too, but does all the work up front and needs everything at once.
- **Quickselect** finds the k-th item in O(n) average time when all the data is in memory.
- **Balanced search trees** support the same operations plus ordered queries, with more overhead.
- **Dijkstra's algorithm** is built around a min-heap, but the heap is the tool, not the whole pattern.
