import { type FormEvent, useState } from 'react'
import { ApiError, api } from '../api/client'

function browserTimeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
  } catch {
    return 'UTC'
  }
}

export default function AuthForm({ onAuthed }: { onAuthed: (token: string) => void }) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const { access_token } =
        mode === 'login' ? await api.login(email, password) : await api.register(email, password, browserTimeZone())
      onAuthed(access_token)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong')
    } finally {
      setBusy(false)
    }
  }

  const isLogin = mode === 'login'
  return (
    <form className="card auth" onSubmit={submit}>
      <h2>{isLogin ? 'Log in' : 'Create an account'}</h2>
      <label>
        Email
        <input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
      </label>
      <label>
        Password
        <input
          type="password"
          autoComplete={isLogin ? 'current-password' : 'new-password'}
          required
          minLength={isLogin ? undefined : 8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </label>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <button type="submit" disabled={busy}>
        {isLogin ? 'Log in' : 'Sign up'}
      </button>
      <button type="button" className="link" onClick={() => setMode(isLogin ? 'register' : 'login')}>
        {isLogin ? 'New here? Create an account' : 'Have an account? Log in'}
      </button>
    </form>
  )
}
