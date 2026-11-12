import { render, screen, within } from '@testing-library/react'
import { expect, test } from 'vitest'
import ProgressCard from './ProgressCard'

test('shows the streak numbers and nudges until today is done', () => {
  const { rerender } = render(<ProgressCard streak={{ current: 3, longest: 5, freezes: 1, done_today: false }} />)
  const streak = screen.getByText('Streak').closest('div')!
  expect(within(streak).getByText('3')).toBeInTheDocument()
  expect(within(screen.getByText('Longest').closest('div')!).getByText('5')).toBeInTheDocument()
  expect(screen.getByText(/keep your streak/)).toBeInTheDocument()
  rerender(<ProgressCard streak={{ current: 4, longest: 5, freezes: 1, done_today: true }} />)
  expect(screen.getByText(/See you tomorrow/)).toBeInTheDocument()
})
