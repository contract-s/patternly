import type { Streak } from '../api/types'

/** The streak as three numbers, plus whether today counts yet. */
export default function ProgressCard({ streak }: { streak: Streak }) {
  return (
    <aside className="card progress" aria-label="Your progress">
      <h3>Your progress</h3>
      <dl className="stats">
        <div>
          <dt>Streak</dt>
          <dd>{streak.current}</dd>
        </div>
        <div>
          <dt>Longest</dt>
          <dd>{streak.longest}</dd>
        </div>
        <div>
          <dt>Freezes</dt>
          <dd>{streak.freezes}</dd>
        </div>
      </dl>
      <p className={`today ${streak.done_today ? 'done' : ''}`}>
        {streak.done_today ? "Today's lesson is done. See you tomorrow." : "Finish today's lesson to keep your streak."}
      </p>
    </aside>
  )
}
