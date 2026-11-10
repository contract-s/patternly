# Kruskal's algorithm

## When to reach for it

- You have places and possible connections between them, each with a cost.
- You need every place connected (directly or through others) for the least total cost.
- You don't care about the distance between any two particular places, only the total spent.
- Variants: grouping items into k clusters by leaving out the k − 1 most expensive connections of the cheapest network.

## The idea

The cheapest network that connects everything never contains a loop, because removing any one connection of a loop keeps everything connected and saves money. So the answer is a tree: n places joined by exactly n − 1 connections.

Build it greedily. Sort the connections from cheapest to most expensive. Walk the list and take a connection if it joins two places that aren't connected yet; skip it if both ends are already in the same group, because it would only make a loop. Taking the cheapest safe connection at each step is always part of some cheapest network, so the greedy choice never has to be undone.

To check "already in the same group" quickly, use a union-find (disjoint set) structure. Each group has a representative; `find` returns it and `union` merges two groups.

## Steps

1. Sort all connections by cost.
2. Put every place in its own group.
3. For each connection in order:
   - If `find(a) != find(b)`, keep the connection and `union(a, b)`.
   - Otherwise skip it.
4. Stop after keeping n − 1 connections. If you run out first, the places can't all be connected.

## Cost

O(E log E) time, dominated by the sort. Union-find with path compression and union by size makes each check nearly constant. O(V) space for union-find, plus the list of connections.

## Common mistakes

- Never sorting, or walking the connections in input order. You get some network, not the cheapest.
- Checking for loops by searching the graph each time, which is slow; union-find makes that check cheap.
- Picking each place's cheapest connection independently. That can leave the places in separate clusters.
- Confusing it with shortest paths. The cheapest network can force a long route between two particular places.

## Easily confused with

- **Prim's algorithm** builds the same cheapest network by growing one tree outward from a start, using a priority queue of connections leaving the tree. Both are valid.
- **Dijkstra's algorithm** minimizes the distance from one start to each place, not the total cost of the network.
- **Breadth- or depth-first search** can find some connecting tree, but ignore costs.
