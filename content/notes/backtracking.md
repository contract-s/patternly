# Backtracking

## When to reach for it

- You need to list every valid arrangement, or find any one, under constraints: assignments, orderings, selections, placements.
- The answer is built from a sequence of choices, and some partial choices can already be ruled out.
- The input is small enough that exponential search is acceptable, usually because no polynomial method is known.

## The idea

Build a solution one choice at a time. At each step, try each option that doesn't break a constraint so far: make the choice, recurse to make the next one, then undo the choice and try the next option. When every choice has been made, you have a complete solution: record it or stop.

The undo step is what makes it work with one shared state. The power comes from pruning: checking constraints as early as possible, so a hopeless partial solution is abandoned before its whole subtree is explored. Good choice order helps too. Picking the most constrained item first (the one with the fewest options left) usually cuts the tree down the most.

## Steps

1. Decide what a partial solution is and what choices extend it.
2. Write `search(partial)`:
   - If the partial solution is complete, record it (or return it if one is enough).
   - Pick the next item to decide.
   - For each option that keeps every constraint: apply it, call `search`, then undo it.
3. Add pruning: reject an option as soon as it conflicts with what's already chosen, and stop a branch when it can no longer reach a solution.
4. To avoid duplicates, impose an order, such as only choosing items in increasing index order.

## Cost

Exponential in the worst case: up to (options per step)^(steps), or n! for orderings. Pruning often makes it fast in practice but doesn't change the worst case. Space is O(depth) for the recursion and the current partial solution.

## Common mistakes

- Generating every complete arrangement first and checking validity only at the end, which loses all the benefit of pruning.
- Forgetting to undo a choice, so state leaks from one branch into the next.
- Not saying when a branch is abandoned. "Try everything" isn't a plan until you say what gets cut early.
- Producing the same solution several times in different orders.
- Claiming polynomial running time.

## Easily confused with

- **Depth-first search** also goes deep and backs up, but visits each node of a fixed graph once. Backtracking explores a tree of choices and undoes them.
- **Dynamic programming** shares answers between overlapping subproblems to count or optimize. Backtracking enumerates actual solutions, without sharing.
- **Greedy algorithms** commit to one option per step and never undo it.
