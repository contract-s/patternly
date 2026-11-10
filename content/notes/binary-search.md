# Binary search

## When to reach for it

- You can ask a yes/no question about a position or a value, and the answer flips exactly once: all "no" then all "yes" (or the reverse).
- Checking one candidate is cheap or affordable, but checking all of them isn't.
- The data is sorted, or the candidates are a range of numbers (a capacity, a speed, a time) where "is this enough?" only goes from no to yes as the number grows.

## The idea

Keep a range that's guaranteed to contain the flip point. Test the middle. If the answer there is "yes", the flip is at the middle or before it; if "no", it's after. Throw away the half that can't hold the flip. Each test halves the range, so about log₂(n) tests find it.

The second form, often called searching on the answer, applies the same idea to a range of possible answers rather than an array. You write a check `feasible(x)` and search for the smallest `x` where it returns true.

## Steps

1. Pick `lo` and `hi` so the flip point is surely inside: `lo` is a known "no" (or the smallest candidate) and `hi` a known "yes" (or the largest).
2. While the range has more than one candidate:
   - Let `mid` be halfway between `lo` and `hi`.
   - If `mid` answers "yes", set `hi = mid`. Otherwise set `lo = mid + 1`.
3. The remaining candidate is the first "yes".

## Cost

O(log n) tests. Total time is O(log n × the cost of one test): O(log n) on a sorted array, O(n log R) when each feasibility check scans n items over a range of size R. O(1) extra space.

## Common mistakes

- Using it when the answer doesn't flip exactly once. If "yes" and "no" are mixed, halving can throw away the answer.
- Off-by-one loops: `lo = mid` together with a rounded-down `mid` can loop forever. Decide whether bounds are inclusive and keep it consistent.
- Getting the starting range wrong, so the answer is outside it.
- Never explaining why it's correct. The key sentence is "the answer flips once, so one test tells you which half to keep."
- Scanning one step at a time from a good guess, which is linear, not logarithmic.

## Easily confused with

- **Linear search** checks candidates one by one. It works on anything but costs O(n) tests.
- **Doubling (galloping) search** first doubles an index until it overshoots, then halves inside that range. It's useful when the upper bound is unknown, at roughly twice the tests.
- **Ternary search** looks for the peak of a function that rises then falls, which is a different shape than a single flip.
