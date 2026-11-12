import type { Lesson, Reveal } from '../api/types'

function formatDate(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { weekday: 'long', month: 'short', day: 'numeric' })
}

interface Props {
  reveal: Reveal
  status: Lesson['status']
  nextReview: string | null
}

/** Shown when the lesson ends: the pattern's name, a short explanation, a reference solution, and its cost. */
export default function RevealPanel({ reveal, status, nextReview }: Props) {
  return (
    <section className="card reveal" aria-label="Pattern reveal">
      <p className="eyebrow">{status === 'passed' ? 'Nice work. The pattern is' : 'Out of tries. The pattern is'}</p>
      <h2>{reveal.pattern}</h2>
      {reveal.summary && <p>{reveal.summary}</p>}
      <h3>One way to solve it</h3>
      <p className="prompt">{reveal.reference_solution}</p>
      <dl className="cost">
        <dt>Time</dt>
        <dd>{reveal.time_complexity}</dd>
        <dt>Space</dt>
        <dd>{reveal.space_complexity}</dd>
      </dl>
      {nextReview && <p className="muted">This pattern comes back for review on {formatDate(nextReview)}.</p>}
    </section>
  )
}
