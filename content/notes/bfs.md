# Breadth-first search

## When to reach for it

- The problem is about things connected to other things (places, people, states, grid cells), so it's a graph even if nobody says "graph".
- You want the fewest steps, hops or moves, and every step counts the same.
- You want to process things in rounds or levels: everything one step away, then everything two steps away, and so on.

## The idea

Explore outward from the start in rings. Use a first-in, first-out queue: take the oldest node out, and add each neighbor not seen before to the back. Because nodes come out in the order they were found, every node one step away is handled before any node two steps away. So in an unweighted graph, the first time you reach a node, you reached it by a path with the fewest edges.

Mark a node as seen when you add it to the queue, not when you take it out, so it can't be added twice. To recover the path, remember which node each one was reached from.

## Steps

1. Put the start node in the queue, mark it seen, and set its distance to 0.
2. While the queue isn't empty:
   - Take the node at the front.
   - For each neighbor not yet seen: mark it seen, set its distance to this node's distance + 1, record this node as its parent, and add it to the back.
3. To process level by level, note the queue's length at the start of each round and handle exactly that many nodes.
4. Starting with several nodes in the queue at distance 0 (a multi-source search) gives each node its distance to the nearest source.

## Cost

O(V + E) time: each node is queued once and each edge is looked at once (twice if undirected). O(V) space for the queue and the seen set.

## Common mistakes

- Using a stack or recursion. That's depth-first search, and it finds a path, not the shortest one.
- Marking nodes seen only when taken off the queue, so the same node gets queued many times.
- Using it when steps have different costs. Fewest edges isn't cheapest total then; you need Dijkstra's algorithm.
- Not saying what the nodes and edges are. "Search from the start" isn't a plan until you say what a node is and what makes two nodes neighbors.

## Easily confused with

- **Depth-first search** goes deep along one path first. Good for reachability, regions and cycles, but not fewest-step paths.
- **Dijkstra's algorithm** is the weighted generalization: a priority queue instead of a plain queue.
- **Topological sort (Kahn's version)** also works in rounds with a queue, but on directed dependency graphs and by counting incoming edges.
