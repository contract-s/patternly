import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { attempt } from '../test/fixtures'
import Critique from './Critique'

test('failed try: ideas covered and the hint with its level', () => {
  render(<Critique attempt={attempt({ attempt: 2, hint_level: 2, hint: 'Think about the left end.' })} />)
  expect(screen.getByRole('heading', { name: 'Try 2: not yet' })).toBeInTheDocument()
  expect(screen.getByText('You covered 1 of 4 key ideas.')).toBeInTheDocument()
  expect(screen.getByText('Keeps a running count.')).toBeInTheDocument()
  expect(screen.getByText('Shape:')).toBeInTheDocument()
  expect(screen.getByText(/Think about the left end/)).toBeInTheDocument()
})

test('passed try: no hint', () => {
  render(<Critique attempt={attempt({ verdict: 'pass', hint: '', hint_level: null, ideas_hit: ['a', 'b'] })} />)
  expect(screen.getByRole('heading', { name: 'Try 1: you got it' })).toBeInTheDocument()
  expect(screen.queryByText(/Nudge|Shape|Strong clue/)).not.toBeInTheDocument()
})
