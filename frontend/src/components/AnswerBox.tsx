import { type FormEvent, useState } from 'react'

interface Props {
  attemptsLeft: number
  /** Tries per lesson, for the dots; the API allows 4. */
  totalAttempts?: number
  busy: boolean
  onSubmit: (answer: string) => void
  /** Earlier answer to start from, so a hint means revising rather than retyping. */
  initial?: string
}

export default function AnswerBox({ attemptsLeft, totalAttempts = 4, busy, onSubmit, initial = '' }: Props) {
  const [answer, setAnswer] = useState(initial)

  function submit(e: FormEvent) {
    e.preventDefault()
    if (answer.trim()) onSubmit(answer.trim())
  }

  return (
    <form className="card answer" onSubmit={submit}>
      <label htmlFor="answer">Your explanation</label>
      <textarea
        id="answer"
        rows={8}
        maxLength={5000}
        value={answer}
        onChange={(e) => setAnswer(e.target.value)}
        placeholder="What would you keep track of, and how would you move through the input?"
        disabled={busy}
      />
      <div className="row">
        <span className="tries muted">
          <span className="tries-dots" aria-hidden="true">
            {Array.from({ length: Math.max(totalAttempts, attemptsLeft) }, (_, i) => (
              <span key={i} className={i < attemptsLeft ? 'left' : 'used'} />
            ))}
          </span>
          {attemptsLeft} {attemptsLeft === 1 ? 'try' : 'tries'} left
        </span>
        <button type="submit" disabled={busy || !answer.trim()}>
          {busy ? 'Grading…' : 'Check my explanation'}
        </button>
      </div>
    </form>
  )
}
