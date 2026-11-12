import { useCallback, useEffect, useState } from 'react'
import { ApiError, api, getToken, setToken } from './api/client'
import type { Me, Streak } from './api/types'
import AuthForm from './components/AuthForm'
import LessonPage from './components/LessonPage'
import Logo from './components/Logo'
import ReminderSettings from './components/ReminderSettings'
import ReviewQueue from './components/ReviewQueue'
import StreakBadge from './components/StreakBadge'

export default function App() {
  const [token, setTokenState] = useState(getToken)
  const [streak, setStreak] = useState<Streak | null>(null)
  const [me, setMe] = useState<Me | null>(null)
  // Bumped after each graded try, so the review queue reloads when a lesson finishes.
  const [graded, setGraded] = useState(0)

  const onStreak = useCallback((s: Streak) => {
    setStreak(s)
    setGraded((n) => n + 1)
  }, [])

  function signIn(t: string) {
    setToken(t)
    setTokenState(t)
  }

  const signOut = useCallback(() => {
    setToken(null)
    setTokenState(null)
    setStreak(null)
    setMe(null)
  }, [])

  useEffect(() => {
    if (!token) return
    let live = true
    api.me().then(
      (m) => {
        if (!live) return
        setMe(m)
        setStreak(m.streak)
      },
      (err) => live && err instanceof ApiError && err.status === 401 && signOut(),
    )
    return () => {
      live = false
    }
  }, [token, signOut])

  return (
    <div className="app">
      <header className="topbar">
        <h1>
          <Logo />
        </h1>
        {token && (
          <nav>
            {streak && <StreakBadge streak={streak} />}
            <button type="button" className="link" onClick={signOut}>
              Log out
            </button>
          </nav>
        )}
      </header>
      <main>
        {token ? (
          <>
            <LessonPage onStreak={onStreak} onUnauthorized={signOut} />
            <ReviewQueue version={graded} />
            {me && <ReminderSettings key={me.id} initial={me.reminders} timezone={me.timezone} />}
          </>
        ) : (
          <>
            <section className="intro">
              <h2>One algorithm pattern a day, learned by explaining it.</h2>
              <p className="muted">
                Read a short scenario, explain how you'd solve it in plain words, and get feedback from a tutor
                that won't give the answer away. About ten minutes a day.
              </p>
            </section>
            <AuthForm onAuthed={signIn} />
          </>
        )}
      </main>
    </div>
  )
}
