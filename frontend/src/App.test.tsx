import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { api, setToken } from './api/client'
import { lesson } from './test/fixtures'
import App from './App'

test('shows the login form when signed out', () => {
  render(<App />)
  expect(screen.getByRole('heading', { name: 'Patternly' })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Log in' })).toBeInTheDocument()
})

afterEach(() => vi.restoreAllMocks())

test('signed in: shows today\'s lesson', async () => {
  setToken('tok')
  vi.spyOn(api, 'today').mockResolvedValue(lesson())
  vi.spyOn(api, 'me').mockResolvedValue({
    id: 1,
    email: 'me@x.test',
    timezone: 'UTC',
    streak: { current: 3, longest: 3, freezes: 0, done_today: false },
  })
  render(<App />)
  expect(await screen.findByRole('heading', { name: 'Longest calm stretch' })).toBeInTheDocument()
  expect(await screen.findByText(/3 days/)).toBeInTheDocument()
})

test('log out clears the token', async () => {
  setToken('tok')
  vi.spyOn(api, 'today').mockResolvedValue(lesson())
  vi.spyOn(api, 'me').mockRejectedValue(new Error('offline'))
  render(<App />)
  await userEvent.click(screen.getByRole('button', { name: 'Log out' }))
  expect(localStorage.getItem('patternly.token')).toBeNull()
  expect(screen.getByRole('heading', { name: 'Log in' })).toBeInTheDocument()
})
