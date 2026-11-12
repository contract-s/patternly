// Shapes returned by the API (backend/src/patternly/service/app.py).

export interface Token {
  access_token: string
  token_type: 'bearer'
}

export interface Streak {
  current: number
  longest: number
  freezes: number
  done_today: boolean
}

export interface Reminders {
  enabled: boolean
  hour: number // local hour the email goes out, 0-23
}

export interface Me {
  id: number
  email: string
  timezone: string
  streak: Streak
  reminders: Reminders
}

export interface Attempt {
  attempt: number
  answer: string
  verdict: 'pass' | 'fail'
  ideas_hit: string[]
  ideas_total: number
  hint: string
  hint_level: number | null
}

export interface Reveal {
  pattern: string
  summary: string | null
  reference_solution: string
  time_complexity: string
  space_complexity: string
}

export interface Lesson {
  date: string
  kind: 'new' | 'review' | 'practice'
  status: 'open' | 'passed' | 'revealed'
  scenario: { id: string; title: string; prompt: string }
  attempts: Attempt[]
  attempts_left: number
  reveal: Reveal | null
  next_review: string | null
}

export interface SubmitResult {
  attempt: Attempt
  lesson: Lesson
  streak: Streak
}

export interface Review {
  pattern: string
  name: string
  box: number
  due: string
  last_outcome: 'clean' | 'hinted' | 'missed'
}

export interface Reviews {
  due: Review[]
  upcoming: Review[]
}
