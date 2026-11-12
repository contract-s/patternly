import type { Lesson } from '../api/types'

const STEPS = ['Read', 'Explain', 'Reveal'] as const

/** Where today's lesson is: reading is done once it loads, explaining runs until the reveal. */
export default function Steps({ status }: { status: Lesson['status'] }) {
  const current = status === 'open' ? 1 : 3 // index of the active step; 3 means all done
  return (
    <ol className="steps" aria-label="Lesson progress">
      {STEPS.map((name, i) => {
        const state = i < current ? 'done' : i === current ? 'current' : 'todo'
        return (
          <li key={name} className={state} aria-current={state === 'current' ? 'step' : undefined}>
            <span className="dot" aria-hidden="true">
              {state === 'done' ? '✓' : i + 1}
            </span>
            {name}
          </li>
        )
      })}
    </ol>
  )
}
