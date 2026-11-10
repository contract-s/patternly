# Dijkstra's algorithm

## When to reach for it

- You need the cheapest, fastest or shortest total path in a network where connections have different costs.
- Every cost is zero or positive.
- You want the best path from one start to one target or to every node.

## The idea

Grow a set of nodes whose best distance is final, always finalizing the closest one next. Keep a tentative distance for every node: 0 for the start and infinity for the rest. Repeatedly take the unfinished node with the smallest tentative distance. Its distance is now final: any other route would have to pass through a node that's already at least as far away, and since costs can't be negative, that route can't come out shorter. Then relax its outgoing edges: if going through this node gives a neighbor a shorter distance, lower that neighbor's tentative distance.

A min-priority queue (heap) gives the smallest tentative distance quickly. Most implementations push a new entry whenever a distance drops and, when an entry comes out, skip it if it's out of date.

## Steps

1. Set `dist[start] = 0` and every other distance to infinity. Push `(0, start)` on a min-heap.
2. While the heap isn't empty:
   - Pop the entry `(d, u)` with the smallest distance. If `d > dist[u]`, it's stale; skip it.
   - For each edge `u → v` with cost `w`: if `d + w < dist[v]`, set `dist[v] = d + w`, record `u` as `v`'s parent, and push `(dist[v], v)`.
3. Stop early when the target is popped if you only need one target.
4. Follow parents back from the target to recover the path.

## Cost

O((V + E) log V) time with a binary heap. O(V + E) space for distances, parents and heap entries.

## Common mistakes

- Using it with negative costs. A finalized distance can then be beaten later, and the answer is wrong.
- Using a plain queue (breadth-first search) on weighted edges, which minimizes the number of edges, not the total cost.
- Finalizing a node when it's pushed rather than when it's popped.
- Scanning all nodes for the minimum each step without saying the cost: O(V²), which is fine for dense graphs but slow for big sparse ones.
- Never explaining why the popped node is final. The key sentence is "no cost is negative, so nothing found later can be shorter."

## Easily confused with

- **Breadth-first search** is the special case where every edge costs the same.
- **Bellman-Ford** handles negative costs and detects negative cycles, at O(V·E) time.
- **Kruskal's and Prim's algorithms** minimize the total cost of a network that connects everything, not the distance from one start.
- **A\*** adds an estimate of the remaining distance to steer toward one target.
