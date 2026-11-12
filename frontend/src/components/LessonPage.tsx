import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, api } from '../api/client'
import type { Lesson, Streak } from '../api/types'
import AnswerBox from './AnswerBox'
import Critique from './Critique'
import LessonCard from './LessonCard'
import RevealPanel from './RevealPanel'

interface Props {
  onStreak: (streak: Streak) => void
  onUnauthorized: () => void
}

/** Today's lesson: the scenario, the learner's tries with feedback, and the reveal when it ends. */
export default function LessonPage({ onStreak, onUnauthorized }: Props) {
  const [lesson, setLesson] = useState<Lesson | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Kept in a ref so `fail` stays stable even if the parent passes a new function each render.
  const unauthorized = useRef(onUnauthorized)
  useEffect(() => {
    unauthorized.current = onUnauthorized
  }, [onUnauthorized])

  const fail = useCallback((err: unknown) => {
    if (err instanceof ApiError && err.status === 401) unauthorized.current()
    else setError(err instanceof ApiError ? err.message : 'Something went wrong')
  }, [])

  useEffect(() => {
    let live = true
    api.today().then(
      (l) => live && setLesson(l),
      (err) => live && fail(err),
    )
    return () => {
      live = false
    }
  }, [fail])

  async function submit(answer: string) {
    setBusy(true)
    setError(null)
    try {
      const result = await api.submit(answer)
      setLesson(result.lesson)
      onStreak(result.streak)
    } catch (err) {
      fail(err)
    } finally {
      setBusy(false)
    }
  }

  if (!lesson) {
    return error ? (
      <p className="error" role="alert">
        {error}
      </p>
    ) : (
      <p className="muted">Loading today's lesson…</p>
    )
  }
  const last = lesson.attempts.at(-1)
  return (
    <div className="stack">
      <LessonCard lesson={lesson} />
      {/* When the lesson is over, the reveal goes first so it isn't buried under the earlier tries. */}
      {lesson.status !== 'open' && lesson.reveal && (
        <RevealPanel reveal={lesson.reveal} status={lesson.status} nextReview={lesson.next_review} />
      )}
      {[...lesson.attempts].reverse().map((a) => (
        <Critique key={a.attempt} attempt={a} />
      ))}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {lesson.status === 'open' && (
        <AnswerBox
          key={lesson.attempts.length}
          attemptsLeft={lesson.attempts_left}
          busy={busy}
          onSubmit={submit}
          initial={last?.answer}
        />
      )}
    </div>
  )
}
