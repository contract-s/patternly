import { useCallback, useEffect, useState } from 'react'
import { ApiError, api, getToken, setToken } from './api/client'
import type { Me, Streak } from './api/types'
import AuthForm from './components/AuthForm'
import Intro from './components/Intro'
import LessonPage from './components/LessonPage'
import Logo from './components/Logo'
import ProgressCard from './components/ProgressCard'
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
    <>
      <header className="topbar">
        <div className="topbar-inner">
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
        </div>
      </header>
      {token ? (
        <main className="app layout">
          <div className="main-col">
            <LessonPage onStreak={onStreak} onUnauthorized={signOut} />
          </div>
          <div className="side-col">
            {streak && <ProgressCard streak={streak} />}
            <ReviewQueue version={graded} />
            {me && <ReminderSettings key={me.id} initial={me.reminders} timezone={me.timezone} />}
          </div>
        </main>
      ) : (
        <main className="app landing">
          <Intro />
          <AuthForm onAuthed={signIn} />
        </main>
      )}
    </>
  )
}
