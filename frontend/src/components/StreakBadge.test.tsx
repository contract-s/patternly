import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import StreakBadge from './StreakBadge'

test('shows days, freezes, and whether today is done', () => {
  const { container } = render(<StreakBadge streak={{ current: 8, longest: 10, freezes: 1, done_today: false }} />)
  expect(screen.getByText(/8 days/)).toBeInTheDocument()
  expect(screen.getByText(/1 🧊/)).toBeInTheDocument()
  const badge = container.querySelector('.streak')!
  expect(badge).toHaveClass('pending')
  expect(badge.getAttribute('title')).toContain('Longest: 10')
  expect(badge.getAttribute('title')).toContain("Finish today's lesson")
})

test('singular day, no freezes', () => {
  render(<StreakBadge streak={{ current: 1, longest: 1, freezes: 0, done_today: true }} />)
  expect(screen.getByText(/1 day$/)).toBeInTheDocument()
  expect(screen.queryByText(/🧊/)).not.toBeInTheDocument()
})
