import type { Attempt } from '../api/types'

const LEVEL_LABEL: Record<number, string> = { 1: 'Nudge', 2: 'Shape', 3: 'Strong clue' }

/** The tutor's feedback on one attempt: which key ideas the learner stated, and a hint if they failed. */
export default function Critique({ attempt }: { attempt: Attempt }) {
  const hit = attempt.ideas_hit.length
  const passed = attempt.verdict === 'pass'
  return (
    <section className={`card critique ${passed ? 'pass' : 'fail'}`} aria-label={`Feedback on try ${attempt.attempt}`}>
      <h3>
        Try {attempt.attempt}: {passed ? 'you got it' : 'not yet'}
      </h3>
      <p>
        You covered {hit} of {attempt.ideas_total} key ideas.
      </p>
      {hit > 0 && (
        <ul className="ideas">
          {attempt.ideas_hit.map((idea) => (
            <li key={idea}>{idea}</li>
          ))}
        </ul>
      )}
      {!passed && attempt.hint && (
        <p className="hint">
          <strong>{LEVEL_LABEL[attempt.hint_level ?? 1] ?? 'Hint'}:</strong> {attempt.hint}
        </p>
      )}
    </section>
  )
}
