import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { ApiError, api } from '../api/client'
import AuthForm from './AuthForm'

afterEach(() => vi.restoreAllMocks())

async function fill(email: string, password: string) {
  await userEvent.type(screen.getByLabelText('Email'), email)
  await userEvent.type(screen.getByLabelText('Password'), password)
}

test('logs in and hands back the token', async () => {
  const login = vi.spyOn(api, 'login').mockResolvedValue({ access_token: 'tok', token_type: 'bearer' })
  const onAuthed = vi.fn()
  render(<AuthForm onAuthed={onAuthed} />)
  await fill('me@x.test', 'longenough')
  await userEvent.click(screen.getByRole('button', { name: 'Log in' }))
  expect(login).toHaveBeenCalledWith('me@x.test', 'longenough')
  expect(onAuthed).toHaveBeenCalledWith('tok')
})

test('registers with the browser time zone', async () => {
  const register = vi.spyOn(api, 'register').mockResolvedValue({ access_token: 'tok', token_type: 'bearer' })
  render(<AuthForm onAuthed={vi.fn()} />)
  await userEvent.click(screen.getByRole('button', { name: /create an account/i }))
  await fill('me@x.test', 'longenough')
  await userEvent.click(screen.getByRole('button', { name: 'Sign up' }))
  expect(register).toHaveBeenCalledWith('me@x.test', 'longenough', Intl.DateTimeFormat().resolvedOptions().timeZone)
})

test('shows the API error', async () => {
  vi.spyOn(api, 'login').mockRejectedValue(new ApiError(401, 'Wrong email or password'))
  const onAuthed = vi.fn()
  render(<AuthForm onAuthed={onAuthed} />)
  await fill('me@x.test', 'nope-nope')
  await userEvent.click(screen.getByRole('button', { name: 'Log in' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Wrong email or password')
  expect(onAuthed).not.toHaveBeenCalled()
})
