import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test } from 'vitest'
import { setToken } from './api/client'
import App from './App'

test('shows the login form when signed out', () => {
  render(<App />)
  expect(screen.getByRole('heading', { name: 'Patternly' })).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Log in' })).toBeInTheDocument()
})

test('log out clears the token', async () => {
  setToken('tok')
  render(<App />)
  await userEvent.click(screen.getByRole('button', { name: 'Log out' }))
  expect(localStorage.getItem('patternly.token')).toBeNull()
  expect(screen.getByRole('heading', { name: 'Log in' })).toBeInTheDocument()
})
