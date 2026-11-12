import type { Streak } from '../api/types'

export default function StreakBadge({ streak }: { streak: Streak }) {
  const days = `${streak.current} ${streak.current === 1 ? 'day' : 'days'}`
  const title =
    `Longest: ${streak.longest}. ` +
    (streak.freezes ? `${streak.freezes} streak ${streak.freezes === 1 ? 'freeze' : 'freezes'} saved.` : '') +
    (streak.done_today ? '' : " Finish today's lesson to keep it going.")
  return (
    <span className={`streak ${streak.done_today ? 'done' : 'pending'}`} title={title.trim()}>
      <span aria-hidden="true">🔥</span> {days}
      {streak.freezes > 0 && <span className="freezes"> · {streak.freezes} 🧊</span>}
    </span>
  )
}
