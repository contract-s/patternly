/** The Patternly mark (same shape as public/favicon.svg) and wordmark. */
export default function Logo() {
  return (
    <span className="logo">
      <svg viewBox="0 0 32 32" width="28" height="28" aria-hidden="true">
        <rect width="32" height="32" rx="8" fill="var(--accent)" />
        <circle cx="11" cy="11" r="3.2" fill="var(--accent-text)" />
        <circle cx="21" cy="11" r="3.2" fill="var(--accent-text)" opacity=".45" />
        <circle cx="11" cy="21" r="3.2" fill="var(--accent-text)" opacity=".45" />
        <circle cx="21" cy="21" r="3.2" fill="var(--accent-text)" />
      </svg>
      Patternly
    </span>
  )
}
