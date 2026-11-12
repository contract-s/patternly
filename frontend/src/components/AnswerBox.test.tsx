import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import AnswerBox from './AnswerBox'

test('submits the trimmed answer', async () => {
  const onSubmit = vi.fn()
  render(<AnswerBox attemptsLeft={4} busy={false} onSubmit={onSubmit} />)
  const button = screen.getByRole('button', { name: 'Check my explanation' })
  expect(button).toBeDisabled()
  await userEvent.type(screen.getByLabelText('Your explanation'), '  keep a window  ')
  await userEvent.click(button)
  expect(onSubmit).toHaveBeenCalledWith('keep a window')
  expect(screen.getByText('4 tries left')).toBeInTheDocument()
})

test('starts from the previous answer and locks while grading', () => {
  render(<AnswerBox attemptsLeft={1} busy onSubmit={vi.fn()} initial="first try" />)
  expect(screen.getByLabelText('Your explanation')).toHaveValue('first try')
  expect(screen.getByLabelText('Your explanation')).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Grading…' })).toBeDisabled()
  expect(screen.getByText('1 try left')).toBeInTheDocument()
})
