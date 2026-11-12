import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { ApiError, api } from '../api/client'
import { attempt, lesson, reveal } from '../test/fixtures'
import LessonPage from './LessonPage'

afterEach(() => vi.restoreAllMocks())

const streak = { current: 1, longest: 1, freezes: 0, done_today: true }

test('loads, fails once with a hint, then passes and reveals', async () => {
  vi.spyOn(api, 'today').mockResolvedValue(lesson())
  const tried = attempt({ answer: 'count things' })
  const submit = vi
    .spyOn(api, 'submit')
    .mockResolvedValueOnce({
      attempt: tried,
      lesson: lesson({ attempts: [tried], attempts_left: 3 }),
      streak: { ...streak, current: 0, done_today: false },
    })
    .mockResolvedValueOnce({
      attempt: attempt({ attempt: 2, verdict: 'pass', hint: '', hint_level: null }),
      lesson: lesson({ status: 'passed', attempts_left: 0, reveal, next_review: '2026-11-14' }),
      streak,
    })
  const onStreak = vi.fn()
  render(<LessonPage onStreak={onStreak} onUnauthorized={vi.fn()} />)

  const box = await screen.findByLabelText('Your explanation')
  await userEvent.type(box, 'count things')
  await userEvent.click(screen.getByRole('button', { name: 'Check my explanation' }))
  expect(submit).toHaveBeenCalledWith('count things')
  expect(await screen.findByText(/What happens when the range breaks/)).toBeInTheDocument()
  // The box keeps the previous answer to revise.
  expect(screen.getByLabelText('Your explanation')).toHaveValue('count things')
  expect(screen.getByText('3 tries left')).toBeInTheDocument()

  await userEvent.type(screen.getByLabelText('Your explanation'), ' and shrink')
  await userEvent.click(screen.getByRole('button', { name: 'Check my explanation' }))
  expect(await screen.findByRole('heading', { name: 'Sliding window' })).toBeInTheDocument()
  expect(screen.queryByLabelText('Your explanation')).not.toBeInTheDocument()
  expect(onStreak).toHaveBeenLastCalledWith(streak)
})

test('a finished lesson shows the reveal above the earlier tries', async () => {
  vi.spyOn(api, 'today').mockResolvedValue(
    lesson({ status: 'revealed', attempts_left: 0, reveal, attempts: [attempt(), attempt({ attempt: 2 })] }),
  )
  render(<LessonPage onStreak={vi.fn()} onUnauthorized={vi.fn()} />)
  const revealPanel = await screen.findByRole('region', { name: 'Pattern reveal' })
  const firstTry = screen.getByRole('region', { name: 'Feedback on try 2' })
  expect(revealPanel.compareDocumentPosition(firstTry) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
})

test('errors: 401 signs out, others are shown', async () => {
  vi.spyOn(api, 'today').mockRejectedValue(new ApiError(401, 'Not logged in'))
  const onUnauthorized = vi.fn()
  render(<LessonPage onStreak={vi.fn()} onUnauthorized={onUnauthorized} />)
  await vi.waitFor(() => expect(onUnauthorized).toHaveBeenCalled())
})

test('a grading error is shown and the answer is kept', async () => {
  vi.spyOn(api, 'today').mockResolvedValue(lesson())
  vi.spyOn(api, 'submit').mockRejectedValue(new ApiError(502, "The tutor couldn't grade this attempt"))
  render(<LessonPage onStreak={vi.fn()} onUnauthorized={vi.fn()} />)
  await userEvent.type(await screen.findByLabelText('Your explanation'), 'my idea')
  await userEvent.click(screen.getByRole('button', { name: 'Check my explanation' }))
  expect(await screen.findByRole('alert')).toHaveTextContent("couldn't grade")
  expect(screen.getByLabelText('Your explanation')).toHaveValue('my idea')
})
