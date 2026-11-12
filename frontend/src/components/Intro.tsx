const HOW = [
  { title: 'Read a scenario', text: 'A short, everyday problem with an algorithm pattern hidden inside.' },
  { title: 'Explain it in plain words', text: 'No code. The tutor checks your idea and nudges you without giving it away.' },
  { title: 'Learn the pattern', text: 'See its name, a worked solution, and its cost. It comes back for review later.' },
]

/** The signed-out pitch shown next to the login form. */
export default function Intro() {
  return (
    <section className="intro">
      <p className="kicker">About 10 minutes a day</p>
      <h2>Learn one algorithm pattern a day by explaining it.</h2>
      <ol className="how">
        {HOW.map((step, i) => (
          <li key={step.title}>
            <span className="num" aria-hidden="true">
              {i + 1}
            </span>
            <div>
              <strong>{step.title}</strong>
              <p>{step.text}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}
