import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { lesson } from '../test/fixtures'
import LessonCard from './LessonCard'

test('shows the scenario and lesson kind', () => {
  render(<LessonCard lesson={lesson({ kind: 'review' })} />)
  expect(screen.getByRole('heading', { name: 'Longest calm stretch' })).toBeInTheDocument()
  expect(screen.getByText(/longest stretch of minutes/)).toBeInTheDocument()
  expect(screen.getByText('Review')).toBeInTheDocument()
})
