import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import Steps from './Steps'

test('explaining is the current step while the lesson is open', () => {
  render(<Steps status="open" />)
  expect(screen.getByText('Explain').closest('li')).toHaveAttribute('aria-current', 'step')
  expect(screen.getByText('Read').closest('li')).toHaveClass('done')
  expect(screen.getByText('Reveal').closest('li')).toHaveClass('todo')
})

test('every step is done once the pattern is revealed', () => {
  render(<Steps status="revealed" />)
  for (const name of ['Read', 'Explain', 'Reveal']) {
    expect(screen.getByText(name).closest('li')).toHaveClass('done')
  }
})
