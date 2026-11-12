import { useCallback, useEffect, useState } from 'react'
import { ApiError, api, getToken, setToken } from './api/client'
import type { Streak } from './api/types'
import AuthForm from './components/AuthForm'
import LessonPage from './components/LessonPage'
import StreakBadge from './components/StreakBadge'

export default function App() {
  const [token, setTokenState] = useState(getToken)
  const [streak, setStreak] = useState<Streak | null>(null)

  function signIn(t: string) {
    setToken(t)
    setTokenState(t)
  }

  const signOut = useCallback(() => {
    setToken(null)
    setTokenState(null)
    setStreak(null)
  }, [])

  useEffect(() => {
    if (!token) return
    let live = true
    api.me().then(
      (me) => live && setStreak(me.streak),
      (err) => live && err instanceof ApiError && err.status === 401 && signOut(),
    )
    return () => {
      live = false
    }
  }, [token, signOut])

  return (
    <div className="app">
      <header className="topbar">
        <h1>Patternly</h1>
        {token && (
          <nav>
            {streak && <StreakBadge streak={streak} />}
            <button type="button" className="link" onClick={signOut}>
              Log out
            </button>
          </nav>
        )}
      </header>
      <main>{token ? <LessonPage onStreak={setStreak} onUnauthorized={signOut} /> : <AuthForm onAuthed={signIn} />}</main>
    </div>
  )
}
