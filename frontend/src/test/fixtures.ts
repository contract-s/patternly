import type { Attempt, Lesson, Reveal } from '../api/types'

export const reveal: Reveal = {
  pattern: 'Sliding window',
  summary: 'Grow the right end, shrink the left.',
  reference_solution: 'Keep two indexes...',
  time_complexity: 'O(n)',
  space_complexity: 'O(1)',
}

export function attempt(over: Partial<Attempt> = {}): Attempt {
  return {
    attempt: 1,
    verdict: 'fail',
    ideas_hit: ['Keeps a running count.'],
    ideas_total: 4,
    hint: 'What happens when the range breaks the rule?',
    hint_level: 1,
    ...over,
  }
}

export function lesson(over: Partial<Lesson> = {}): Lesson {
  return {
    date: '2026-11-12',
    kind: 'new',
    status: 'open',
    scenario: { id: 's1', title: 'Longest calm stretch', prompt: 'Find the longest stretch of minutes...' },
    attempts: [],
    attempts_left: 4,
    reveal: null,
    next_review: null,
    ...over,
  }
}
