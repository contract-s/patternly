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
  render(<App />)
  expect(await screen.findByRole('heading', { name: 'Longest calm stretch' })).toBeInTheDocument()
})

test('log out clears the token', async () => {
  setToken('tok')
  vi.spyOn(api, 'today').mockResolvedValue(lesson())
  render(<App />)
  await userEvent.click(screen.getByRole('button', { name: 'Log out' }))
  expect(localStorage.getItem('patternly.token')).toBeNull()
  expect(screen.getByRole('heading', { name: 'Log in' })).toBeInTheDocument()
})
