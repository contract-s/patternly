# Dynamic programming

## When to reach for it

- You're asked for a best value (most, least, cheapest), a count of ways, or whether something is possible.
- The answer for a big input can be built from answers to smaller versions of the same question: a shorter prefix, a smaller amount, fewer items.
- Trying every combination would be exponential, and many combinations share the same smaller questions.
- A greedy choice (always take the biggest or cheapest) can be shown to fail on some input.

## The idea

Name the smaller question precisely. That's the state: "the best value using only the first i items", "the answer for the first i items of one sequence and the first j of another". Then write how the answer to one state comes from smaller states. That's the recurrence, and it usually tries each possible last choice and keeps the best. Finally, compute each state once and store it, so shared subproblems aren't solved again and again.

You can fill a table from the smallest states up (bottom-up, also called tabulation), or write the recursion directly and cache results (top-down, also called memoization). Both cost the same; bottom-up avoids deep recursion and often lets you keep only the last row.

## Steps

1. Define the state in one sentence, including what each index means.
2. Write the recurrence: the choices for the last step and how to combine them (min, max, sum, or/and).
3. Set the base cases, the smallest states you can answer directly, and the value for impossible states (such as infinity for "fewest").
4. Pick an order that computes every state after the states it depends on.
5. Read off the answer from the right state. If you need the choices, not just the value, store which choice won and walk back.

## Cost

Number of states × work per state. For example, target size × number of options, or length × length when comparing two sequences. Space is the table size, often reducible to one or two rows.

## Common mistakes

- Using a greedy rule without proof. Always taking the biggest piece first, for instance, fails for some sets of sizes.
- A vague state ("the best so far") that doesn't say what's included, so the recurrence can't be written.
- Plain recursion without storing results, which repeats work exponentially.
- Wrong base cases or impossible states treated as 0, which makes impossible answers look free.
- Filling the table in an order that reads a state before it's computed.

## Easily confused with

- **Greedy algorithms** commit to one choice per step and never revisit. They're faster when they're provably right; DP is the safe choice when they aren't.
- **Backtracking** also explores choices recursively but doesn't share subproblem answers, so it's exponential. It suits problems where you must list every solution.
- **Divide and conquer** (like merge sort) splits into independent halves that don't overlap, so there's nothing to store.
