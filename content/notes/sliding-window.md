# Sliding window

## When to reach for it

- The question is about a contiguous stretch: a run of consecutive items, a substring, a span of time.
- You want the longest, shortest or best stretch that satisfies a rule, or to count stretches.
- The rule changes predictably as the stretch grows or shrinks. Adding an item can only make it "more broken", and removing one can only help.

## The idea

Describe the current stretch by two indexes, `left` and `right`. Move `right` forward one item at a time to grow the stretch, and keep a small summary of what's inside (a count, a sum, a map of item counts). Whenever the stretch breaks the rule, move `left` forward, removing items from the summary, until it's valid again. After each step, the stretch ending at `right` is the best valid one ending there, so compare it with the best so far.

Neither index ever moves backward, so every item enters the window once and leaves at most once.

## Steps

1. Start with `left = 0`, an empty summary and an empty best answer.
2. For each `right` from first to last:
   - Add the item at `right` to the summary.
   - While the window breaks the rule, remove the item at `left` from the summary and move `left` forward.
   - Record the window if it beats the best so far.
3. For a fixed-size window, move `left` exactly once each time `right` moves, after the window is full.

## Cost

O(n) time, because each index moves forward at most n times. Space is whatever the summary needs: O(1) for a count or sum, O(k) for a map of up to k distinct items.

## Common mistakes

- Restarting the window from scratch when the rule breaks. That throws away valid stretches that overlap the old one.
- Shrinking by just one step when one removal might not be enough. Use a loop, not a single `if`, unless you've shown one step always suffices.
- Recomputing the summary from scratch for every window, which brings back the O(n²) or O(n·k) cost.
- Using it when removing an item can make the window worse, such as sums with negative numbers. Then shrinking isn't safe and you need prefix sums or another method.

## Easily confused with

- **Prefix sums** answer arbitrary range-sum questions and handle negative numbers. A window works only when growing and shrinking change the rule in one direction.
- **Two pointers from both ends** (on sorted data) move toward each other. A window's two indexes both move the same way.
- **Checking every start and end** is the O(n²) brute force a window replaces.
