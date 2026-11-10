# Monotonic stack

## When to reach for it

- For each item in a sequence, you need the next (or previous) item that's greater or smaller.
- You need how far away that item is: how many positions until a higher value, for example.
- You need the largest rectangle that fits under a row of bars, which comes down to finding where each bar's height is first undercut on each side.
- The brute force is "for each item, scan ahead", which is O(n²).

## The idea

Walk the sequence once and keep a stack of items that are still waiting for their answer. Keep the stack ordered: for "next greater", values decrease from bottom to top. When a new item arrives, it's the answer for every waiting item smaller than it, so pop those items and record the new item as their answer. Then push the new item; it waits too. Items left on the stack at the end have no answer.

Store indexes rather than values, so you can compute distances and look values up.

Each item is pushed once and popped at most once, so although there's a loop inside the main loop, the total work is linear.

For the largest rectangle, keep bars in increasing height order. When a shorter bar arrives, every taller bar it pops has just found its right boundary, and the bar under it on the stack is its left boundary. That gives the widest rectangle using the popped bar's full height.

## Steps

1. Start with an empty stack of indexes and every answer set to "none".
2. For each index i:
   - While the stack isn't empty and the item at i beats the item at the top: pop the top index j and record i as j's answer (or i − j as the distance).
   - Push i.
3. Anything left on the stack has no answer.
4. For "previous greater", read the top of the stack after popping and before pushing.

## Cost

O(n) time, since each index is pushed and popped at most once. O(n) space for the stack in the worst case.

## Common mistakes

- Scanning ahead from every item, which is O(n²).
- Keeping the stack in the wrong order, so items are popped by the wrong neighbors.
- Storing values instead of indexes, which loses the distances.
- Getting ties wrong (strictly greater versus greater or equal). Decide which the problem asks for.
- Claiming the inner while loop makes it O(n²) without noticing each item leaves the stack only once.

## Easily confused with

- **Sliding window** also uses one pass and two ends, but tracks a contiguous range with a rule.
- **Heaps** find the overall largest item, not the nearest larger one.
- **A sorted list of items so far** answers "is there a larger one?" but not "which one comes next?".
