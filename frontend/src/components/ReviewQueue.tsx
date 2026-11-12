import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Review, Reviews } from '../api/types'

const OUTCOME_LABEL: Record<Review['last_outcome'], string> = {
  clean: 'solved first try',
  hinted: 'solved with hints',
  missed: 'missed',
}

function when(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function Row({ r }: { r: Review }) {
  return (
    <li>
      <span className="name">{r.name}</span>
      <span className="muted">
        {OUTCOME_LABEL[r.last_outcome]} · box {r.box} · {when(r.due)}
      </span>
    </li>
  )
}

/** Patterns the learner has finished, split into due now and coming up. Reloads when `version` changes. */
export default function ReviewQueue({ version = 0 }: { version?: number }) {
  const [reviews, setReviews] = useState<Reviews | null>(null)

  useEffect(() => {
    let live = true
    api.reviews().then(
      (r) => live && setReviews(r),
      () => {},
    )
    return () => {
      live = false
    }
  }, [version])

  if (!reviews || (reviews.due.length === 0 && reviews.upcoming.length === 0)) return null
  return (
    <aside className="card reviews" aria-label="Review queue">
      <h3>Review queue</h3>
      {reviews.due.length > 0 && (
        <>
          <h4>Due now</h4>
          <ul>
            {reviews.due.map((r) => (
              <Row key={r.pattern} r={r} />
            ))}
          </ul>
        </>
      )}
      {reviews.upcoming.length > 0 && (
        <>
          <h4>Coming up</h4>
          <ul>
            {reviews.upcoming.map((r) => (
              <Row key={r.pattern} r={r} />
            ))}
          </ul>
        </>
      )}
    </aside>
  )
}
