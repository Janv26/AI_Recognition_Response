import { ArrowUp, AudioLines, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { friendlyError, request, API_BASE } from './api'

function GoogleMark() {
  return (
    <svg aria-hidden="true" viewBox="0 0 18 18" className="google-mark">
      <path fill="#4285F4" d="M17.64 9.2c0-.63-.06-1.24-.16-1.82H9v3.44h4.84a4.14 4.14 0 0 1-1.8 2.72v2.23h2.92c1.71-1.58 2.68-3.91 2.68-6.57Z" />
      <path fill="#34A853" d="M9 18c2.43 0 4.47-.81 5.96-2.2l-2.92-2.26c-.81.54-1.84.87-3.04.87-2.34 0-4.33-1.58-5.04-3.71H.95v2.33A9 9 0 0 0 9 18Z" />
      <path fill="#FBBC05" d="M3.96 10.7A5.4 5.4 0 0 1 3.68 9c0-.59.1-1.16.28-1.7V4.97H.95A9 9 0 0 0 0 9c0 1.45.35 2.82.95 4.03l3.01-2.33Z" />
      <path fill="#EA4335" d="M9 3.58c1.32 0 2.5.45 3.43 1.34l2.57-2.57A8.58 8.58 0 0 0 9 0 9 9 0 0 0 .95 4.97l3.01 2.33C4.67 5.16 6.66 3.58 9 3.58Z" />
    </svg>
  )
}

function AuthScreen({ onAuthenticated, externalError, clearError }) {
  const [mode, setMode] = useState('login')
  const [fullname, setFullname] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const message = error || externalError

  async function submit(event) {
    event.preventDefault()
    setError('')

    if (mode === 'signup' && password !== confirmPassword) {
      setError('Those passwords do not match yet.')
      return
    }

    setBusy(true)

    try {
      const payload = mode === 'signup'
        ? { fullname, email, password, confirmPassword }
        : { email, password }

      const result = await request(`/api/auth/${mode}`, {
        method: 'POST',
        body: JSON.stringify(payload),
      })

      onAuthenticated(result)
    } catch (authError) {
      setError(friendlyError(authError))
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="auth-page">
      <div className="auth-grain" />

      <section className="auth-intro">
        <a className="brand auth-brand" href="#home" onClick={(event) => event.preventDefault()}>
          <span className="brand-mark"><AudioLines size={19} strokeWidth={2.4} /></span>
          <span>Make room for possibility<span className="brand-period">...</span></span>
        </a>

        <div className="intro-copy">
          <span className="welcome-kicker"><span className="mini-spark">✳</span> A MORE HUMAN KIND OF AI</span>
          <h1>AI VOICE <em>ASSISTANCE.</em></h1>
          <p>A thoughtful place to ask, explore, and find your next idea.</p>

          <div className="sound-art" aria-hidden="true">
            <div className="sound-art-ring ring-one" />
            <div className="sound-art-ring ring-two" />
            <div className="sound-core"><AudioLines size={31} /></div>
            <span className="sound-caption">LISTEN CLOSELY</span>
          </div>
        </div>

        <div className="auth-footnote"><ShieldCheck size={15} /> Private conversations, always yours.</div>
      </section>

      <section className="auth-side">
        <div className="auth-card">
          <div className="auth-card-heading">
            <h2>{mode === 'login' ? 'Welcome back.' : 'Come on in.'}</h2>
            <p>{mode === 'login' ? 'Pick up where curiosity left off.' : 'A new perspective is one question away.'}</p>
          </div>

          <button
            className="google-button"
            onClick={() => {
              clearError()
              window.location.href = `${API_BASE}/api/auth/google`
            }}
            type="button"
          >
            <GoogleMark /> Continue with Google
          </button>

          <div className="auth-divider"><span /> <small>or with email</small> <span /></div>

          <form onSubmit={submit}>
            {mode === 'signup' && (
              <>
                <label className="field-label" htmlFor="fullname">Full name</label>
                <input id="fullname" autoComplete="name" placeholder="How should we call you?" value={fullname} onChange={(event) => setFullname(event.target.value)} required maxLength={120} />
              </>
            )}

            <label className="field-label" htmlFor="email">Email address</label>
            <input id="email" type="email" autoComplete="email" placeholder="you@example.com" value={email} onChange={(event) => setEmail(event.target.value)} required />

            <label className="field-label" htmlFor="password">Password</label>
            <input id="password" type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} placeholder="At least 8 characters" value={password} onChange={(event) => setPassword(event.target.value)} minLength={8} required />

            {mode === 'signup' && (
              <>
                <label className="field-label" htmlFor="confirm-password">Confirm password</label>
                <input id="confirm-password" type="password" autoComplete="new-password" placeholder="Enter your password again" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} minLength={8} required />
              </>
            )}

            {message && <div className="auth-error" role="alert">{message}</div>}

            <button className="auth-submit" type="submit" disabled={busy}>
              {busy ? 'One moment…' : mode === 'login' ? <>Login<ArrowUp size={17} /></> : <>Sign Up <ArrowUp size={17} /></>}
            </button>
          </form>

          <p className="auth-switch">
            {mode === 'login' ? 'New around here?' : 'Already have an account?'}{' '}
            <button onClick={() => { setMode(mode === 'login' ? 'signup' : 'login'); setError(''); clearError() }}>
              {mode === 'login' ? 'Create an account' : 'Sign in instead'}
            </button>
          </p>
        </div>

        <div className="auth-legal">By continuing, you agree to use AI Voice Assistant thoughtfully. <span>·</span> Made for curious minds.</div>
      </section>
    </main>
  )
}

export default AuthScreen
