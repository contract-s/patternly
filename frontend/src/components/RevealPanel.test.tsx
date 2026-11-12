import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { reveal } from '../test/fixtures'
import RevealPanel from './RevealPanel'

test('shows the pattern, solution, cost, and next review', () => {
  render(<RevealPanel reveal={reveal} status="passed" nextReview="2026-11-14" />)
  expect(screen.getByText('Nice work. The pattern is')).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Sliding window' })).toBeInTheDocument()
  expect(screen.getByText('Keep two indexes...')).toBeInTheDocument()
  expect(screen.getByText('O(n)')).toBeInTheDocument()
  expect(screen.getByText(/comes back for review on .*Nov 14/)).toBeInTheDocument()
})

test('different lead-in when revealed after running out of tries', () => {
  render(<RevealPanel reveal={reveal} status="revealed" nextReview={null} />)
  expect(screen.getByText('Out of tries. The pattern is')).toBeInTheDocument()
  expect(screen.queryByText(/comes back/)).not.toBeInTheDocument()
})
