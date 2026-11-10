# Topological sort

## When to reach for it

- Things depend on other things (tasks, steps, modules) and you need an order where everything comes after what it depends on.
- You need to know whether such an order exists at all, which is the same as asking whether the dependencies contain a cycle.
- You want to schedule in rounds, where each round runs everything whose dependencies are already done.

## The idea

Model the dependencies as a directed graph with an edge from each prerequisite to the thing that needs it. An order where every edge points forward exists exactly when the graph has no cycle.

Kahn's method builds the order by counting. For every node, count its incoming edges, meaning its unfinished prerequisites. Nodes with a count of zero can go now; put them in a queue. Take one out, add it to the order, and lower the count of everything that depends on it. Whenever a count drops to zero, that node is ready, so queue it. If the queue empties before every node is placed, the leftover nodes are waiting on each other, which means there's a cycle.

For rounds, process the queue level by level: everything ready at the start is round 1, everything that becomes ready because of round 1 is round 2, and so on. The number of rounds is the length of the longest dependency chain.

A depth-first version also works. Each node is added to a list when it finishes, after everything reachable from it has finished, and the reversed list is the order.

## Steps

1. Build the graph and count incoming edges for every node.
2. Queue every node with a count of zero.
3. While the queue isn't empty, take a node, append it to the order, and decrement each dependent's count, queuing any that reach zero.
4. If the order has fewer nodes than the graph, report a cycle.

## Cost

O(V + E) time, since each node is queued once and each edge decremented once. O(V + E) space for the graph and the counts.

## Common mistakes

- Getting edge direction backwards, which produces the order reversed.
- Never checking whether every node was placed, so a cycle goes unreported.
- Starting only from one node instead of every node with no prerequisites.
- Sorting by number of prerequisites. That doesn't respect the actual chains.
- Repeatedly scanning all nodes for one that's ready, which is O(V²).

## Easily confused with

- **Depth-first search** can find cycles and produce the order too, using in-progress and finished states.
- **Breadth-first search** also uses a queue and rounds, but measures distance from a start, not readiness.
- **Sorting** compares items by a key. Here there's no key, only "must come before" relationships.
