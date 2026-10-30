import { AudioLines } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import './App.css'
import AuthScreen from './Auth'
import Chat from './Chat'
import SettingsModal from './SettingsModal'
import { request, friendlyError, getStoredUser, makeGroups, TOKEN_KEY, USER_KEY } from './api'

function App() {
  // trail for chat preview:
    const isChatPreview =
    window.location.pathname === '/chat-preview'
  const isPasswordRoute = ['/forgot-password', '/reset-password'].includes(
    window.location.pathname,
  )

  const [previewMessages, setPreviewMessages] = useState([])
  const [previewInput, setPreviewInput] = useState('')
  // end of trail for chat preview
  // 1) Basic app data
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY))
  const [user, setUser] = useState(getStoredUser)
  const [authChecking, setAuthChecking] = useState(Boolean(localStorage.getItem(TOKEN_KEY)))
  const [history, setHistory] = useState([])
  const [conversationId, setConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [listening, setListening] = useState(false)
  const [error, setError] = useState('')
  const [settings, setSettings] = useState({ name: '', language: 'English', voiceEnabled: false })
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [settingsSaving, setSettingsSaving] = useState(false)
  const [serviceOnline, setServiceOnline] = useState(null)
  const messagesEndRef = useRef(null)

  // 2) Auto-scroll to newest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, sending])

  // 3) Check backend health
  useEffect(() => {
    request('/api/health')
      .then(() => setServiceOnline(true))
      .catch(() => setServiceOnline(false))
  }, [])

  // 4) Handle Google login callback from the backend
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const googleCode = params.get('google_code')

    if (!googleCode) return

    params.delete('google_code')
    const query = params.toString()
    window.history.replaceState({}, '', `${window.location.pathname}${query ? `?${query}` : ''}`)

    request('/api/auth/google/exchange', {
      method: 'POST',
      body: JSON.stringify({ code: googleCode }),
    })
      .then(saveSession)
      .catch((err) => setError(friendlyError(err)))
  }, [])

  // 5) Load user data after login
  useEffect(() => {
    if (!token || isPasswordRoute) {
      setAuthChecking(false)
      return
    }

    let active = true

    Promise.all([
      request('/api/chat/history', { token }),
      request('/api/users/settings', { token }),
    ])
      .then(([entries, preferences]) => {
        if (!active) return

        setHistory(makeGroups(entries))
        setSettings({
          name: preferences.name || user?.name || '',
          language: preferences.language || 'English',
          voiceEnabled: Boolean(preferences.voiceEnabled),
        })
      })
      .catch((loadError) => {
        if (!active) return

        if (loadError.message.includes('token') || loadError.message.includes('account')) {
          clearSession()
        } else {
          setError(friendlyError(loadError))
        }
      })
      .finally(() => active && setAuthChecking(false))

    return () => {
      active = false
    }
  }, [token, isPasswordRoute])

  function saveSession(result) {
    const accessToken = result.access_token || result.token

    localStorage.setItem(TOKEN_KEY, accessToken)
    localStorage.setItem(USER_KEY, JSON.stringify(result.user))

    setToken(accessToken)
    setUser(result.user)
    setError('')
    setAuthChecking(true)
  }

  function clearSession() {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)

    setToken(null)
    setUser(null)
    setHistory([])
    setMessages([])
    setConversationId(null)
    setSettingsOpen(false)
  }

  function startConversation() {
    setConversationId(null)
    setMessages([])
    setInput('')
    setError('')
  }

  function openConversation(group) {
    setConversationId(group.id)
    setMessages(
      group.turns.flatMap((turn) => [
        { id: `user-${turn.id}`, role: 'user', content: turn.prompt },
        { id: `assistant-${turn.id}`, role: 'assistant', content: turn.response },
      ]),
    )
    setError('')
  }

  async function sendMessage(rawText, useVoice = false) {
    const text = rawText.trim()
    if (!text || sending) return

    setError('')
    setInput('')
    setMessages((current) => [...current, { id: `draft-${Date.now()}`, role: 'user', content: text }])
    setSending(true)

    try {
      const result = await request(useVoice ? '/api/voice/respond' : '/api/chat', {
        method: 'POST',
        token,
        body: JSON.stringify({ text, conversation_id: conversationId }),
      })

      setConversationId(result.conversation_id)
      setMessages((current) => [
        ...current,
        {
          id: `answer-${Date.now()}`,
          role: 'assistant',
          content: result.response || result.answer,
        },
      ])

      const entries = await request('/api/chat/history', { token })
      setHistory(makeGroups(entries))

      // Voice reply is optional, only if user enabled it
      if (useVoice && settings.voiceEnabled && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel()
        window.speechSynthesis.speak(new SpeechSynthesisUtterance(result.answer))
      }
    } catch (sendError) {
      setError(friendlyError(sendError))
    } finally {
      setSending(false)
    }
  }


const recognitionRef = useRef(null)

function startVoiceInput() {
  const SpeechRecognition =
    window.SpeechRecognition || window.webkitSpeechRecognition

  if (!SpeechRecognition) {
    setError('Voice input is not supported in this browser. Try Chrome or Edge.')
    return
  }

  // Prevent starting another session while one is already listening
  if (recognitionRef.current) {
    return
  }

  const recognition = new SpeechRecognition()
  recognitionRef.current = recognition

  recognition.lang = 'en-US'
  recognition.interimResults = false

  recognition.onstart = () => {
    setListening(true)
    setError('')
  }

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript
    sendMessage(transcript, true)
  }

  recognition.onerror = (event) => {
    console.error('Speech recognition error:', event.error)

    if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
      setError('Microphone access denied. Check your browser permissions.')
    } else if (event.error === 'no-speech') {
      setError('No speech detected. Please try again.')
    } else if (event.error !== 'aborted') {
      setError(`Voice input failed: ${event.error}`)
    }
  }

  recognition.onend = () => {
    setListening(false)
    recognitionRef.current = null
  }

  try {
    recognition.start()
  } catch (error) {
    console.error('Could not start speech recognition:', error)
    setListening(false)
    recognitionRef.current = null
    setError('Could not start voice input. Please try again.')
  }
}


  async function saveSettings(event) {
    event.preventDefault()
    setSettingsSaving(true)
    setError('')

    try {
      const updated = await request('/api/users/settings', {
        method: 'PUT',
        token,
        body: JSON.stringify({
          name: settings.name,
          language: settings.language,
          voiceEnabled: settings.voiceEnabled,
        }),
      })

      const nextUser = { ...user, name: updated.name || user?.name }
      setUser(nextUser)
      localStorage.setItem(USER_KEY, JSON.stringify(nextUser))
      setSettings({
        name: updated.name || '',
        language: updated.language,
        voiceEnabled: updated.voiceEnabled,
      })
      setSettingsOpen(false)
    } catch (settingsError) {
      setError(friendlyError(settingsError))
    } finally {
      setSettingsSaving(false)
    }
  }

  // Temporary chat preview: does not require login or backend access
  if (isChatPreview) {
    function sendPreviewMessage(rawText) {
      const text = rawText.trim()
      if (!text) return

      setPreviewMessages((current) => [
        ...current,
        {
          id: `user-${Date.now()}`,
          role: 'user',
          content: text,
        },
        {
          id: `assistant-${Date.now() + 1}`,
          role: 'assistant',
          content: `This is a local UI preview. Your message was: "${text}". Connect the backend to receive real AI responses.`,
        },
      ])

      setPreviewInput('')
    }

    return (
      <Chat
        user={{ name: 'Preview User', email: 'preview@example.com' }}
        history={[]}
        conversationId={null}
        messages={previewMessages}
        input={previewInput}
        sending={false}
        listening={false}
        error=""
        serviceOnline={false}
        messagesEndRef={messagesEndRef}
        onInputChange={setPreviewInput}
        onSendMessage={sendPreviewMessage}
        onStartConversation={() => {
          setPreviewMessages([])
          setPreviewInput('')
        }}
        onOpenConversation={() => {}}
        onOpenSettings={() => {}}
        onStartVoiceInput={() => {}}
        onClearError={() => {}}
      />
    )
  }

  if (!token || isPasswordRoute) {
    return <AuthScreen onAuthenticated={saveSession} externalError={error} clearError={() => setError('')} />
  }

// end of temporary chat preview
  if (authChecking) {
    return <div className="app-loading"><AudioLines size={25} /><span>Opening your space</span></div>
  }

  return (
    <>
      <Chat
        user={user}
        history={history}
        conversationId={conversationId}
        messages={messages}
        input={input}
        sending={sending}
        listening={listening}
        error={error}
        serviceOnline={serviceOnline}
        messagesEndRef={messagesEndRef}
        onInputChange={setInput}
        onSendMessage={sendMessage}
        onStartConversation={startConversation}
        onOpenConversation={openConversation}
        onOpenSettings={() => setSettingsOpen(true)}
        onStartVoiceInput={startVoiceInput}
        onClearError={() => setError('')}
      />

      <SettingsModal
        open={settingsOpen}
        settings={settings}
        setSettings={setSettings}
        onClose={() => setSettingsOpen(false)}
        onSave={saveSettings}
        onClearSession={clearSession}
        saving={settingsSaving}
      />
    </>
  )
}

export default App
