# Depth-first search

## When to reach for it

- You need to explore everything reachable from a point, such as a connected region in a grid or a group of linked records.
- You need to count separate regions or components.
- You need to find a cycle in a directed graph, or anything else that depends on "the path I'm currently on".
- The path length doesn't matter, only whether something can be reached.

## The idea

From a node, pick one unvisited neighbor and go there, then do the same from that neighbor, going as deep as you can. When a node has no unvisited neighbors left, back up to the previous node and try its next neighbor. Recursion does the backing up for you; an explicit stack works the same way and avoids recursion depth limits.

Keep a visited set so no node is explored twice. To count regions, start a new search from every node not yet visited, and count how many searches you start.

For cycles in a directed graph, a plain visited set isn't enough. Use three states: unvisited, in progress (on the current path) and finished. Reaching an in-progress node means you've looped back onto your own path, which is a cycle. Reaching a finished node is fine; it was fully explored by another path.

## Steps

1. Mark every node unvisited.
2. For each unvisited node, start a search:
   - Mark the node visited (or in progress).
   - For each neighbor: if it's unvisited, search from it. For cycle finding, if it's in progress, report a cycle.
   - When all neighbors are done, mark the node finished.
3. The number of searches started from step 2 is the number of components.

## Cost

O(V + E) time, since each node and edge is handled once. O(V) space for the visited marks and the recursion or stack, which can be as deep as the longest path.

## Common mistakes

- Forgetting the visited set, which loops forever on cycles or redoes work exponentially.
- Using a single visited flag to detect directed cycles. Two separate paths into the same finished node then look like a cycle.
- Starting only from one node when the graph may have several components.
- Expecting it to find shortest paths. The first path it finds is often long.
- Deep recursion on big grids, which can overflow the call stack. An explicit stack fixes it.

## Easily confused with

- **Breadth-first search** explores in rings and finds fewest-step paths. For simply counting regions, either one works.
- **Backtracking** also goes deep and backs up, but it undoes choices to try every combination. Depth-first search visits each node once and never revisits.
- **Union-find** can also count components, by merging groups edge by edge, without walking the graph.
