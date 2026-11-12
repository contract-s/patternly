import type { Lesson } from '../api/types'

const KIND_LABEL: Record<Lesson['kind'], string> = {
  new: 'New pattern',
  review: 'Review',
  practice: 'Practice',
}

export default function LessonCard({ lesson }: { lesson: Lesson }) {
  return (
    <article className="card lesson">
      <p className="eyebrow">
        <span className={`badge ${lesson.kind}`}>{KIND_LABEL[lesson.kind]}</span> Today's lesson
      </p>
      <h2>{lesson.scenario.title}</h2>
      <p className="prompt">{lesson.scenario.prompt}</p>
      <p className="muted">Explain how you'd solve it in plain words. No code needed.</p>
    </article>
  )
}
