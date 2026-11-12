import { useState } from 'react'
import { getToken, setToken } from './api/client'
import AuthForm from './components/AuthForm'

export default function App() {
  const [token, setTokenState] = useState(getToken)

  function signIn(t: string) {
    setToken(t)
    setTokenState(t)
  }

  function signOut() {
    setToken(null)
    setTokenState(null)
  }

  return (
    <div className="app">
      <header className="topbar">
        <h1>Patternly</h1>
        {token && (
          <button type="button" className="link" onClick={signOut}>
            Log out
          </button>
        )}
      </header>
      <main>{token ? <p>Signed in.</p> : <AuthForm onAuthed={signIn} />}</main>
    </div>
  )
}
