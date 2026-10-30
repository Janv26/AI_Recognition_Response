import {
  ArrowUp,
  AudioLines,
  ChevronDown,
  CircleHelp,
  Clock3,
  Command,
  MessageSquareText,
  Mic,
  Plus,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  X,
} from 'lucide-react'
import { useState } from 'react'

function Chat({
  user,
  history,
  conversationId,
  messages,
  input,
  sending,
  listening,
  error,
  serviceOnline,
  messagesEndRef,
  onInputChange,
  onSendMessage,
  onStartConversation,
  onOpenConversation,
  onOpenSettings,
  onStartVoiceInput,
  onClearError,
}) {
  const [historySearch, setHistorySearch] = useState('')
  const activeTitle = history.find((group) => group.id === conversationId)?.turns[0]?.prompt
  const searchTerm = historySearch.trim().toLocaleLowerCase()
  const visibleHistory = (searchTerm
    ? history.filter((group) =>
        group.turns.some((turn) =>
          `${turn.prompt || ''} ${turn.response || ''}`.toLocaleLowerCase().includes(searchTerm),
        ),
      )
    : history.slice(0, 30))

  return (
    <main className="workspace-shell">
      <aside className="sidebar">
        <a className="brand" href="#home" onClick={(event) => event.preventDefault()}>
          <span className="brand-mark"><AudioLines size={19} strokeWidth={2.4} /></span>
          <span>AI Voice Assistant<span className="brand-period">.</span></span>
        </a>

        <button className="new-chat-button" onClick={onStartConversation}>
          <Plus size={17} /> <span>New conversation</span><span className="shortcut">⌘ K</span>
        </button>

        <label className="sidebar-search">
          <Search size={15} aria-hidden="true" />
          <input
            type="text"
            value={historySearch}
            onChange={(event) => setHistorySearch(event.target.value)}
            placeholder="Search conversations"
            aria-label="Search conversations"
          />
          {historySearch
            ? <button type="button" onClick={() => setHistorySearch('')} aria-label="Clear conversation search"><X size={14} /></button>
            : <Command size={12} aria-hidden="true" />}
        </label>

        <div className="history-heading">
          <span>YOUR HISTORY</span>
          
        </div>

        <div className="history-list">
          {visibleHistory.length ? visibleHistory.map((group) => (
            <button
              key={group.id}
              className={`history-item ${conversationId === group.id ? 'selected' : ''}`}
              onClick={() => onOpenConversation(group)}
              title={group.turns[0]?.prompt}
            >
              <MessageSquareText size={15} />
              <span>{group.turns[0]?.prompt || 'Untitled conversation'}</span>
            </button>
          )) : <p className="history-empty">
            {searchTerm
              ? 'No conversations match your search.'
              : 'Your conversations will show up here.'}
          </p>}
        </div>

        <div className="sidebar-bottom">
          <div className="service-status">
            <span className={`status-dot ${serviceOnline === false ? 'offline' : ''}`} />
            {serviceOnline === null ? 'Checking connection' : serviceOnline ? 'All systems ready' : 'API unavailable'}
          </div>

          <button className="account-button" onClick={onOpenSettings}>
            <span className="avatar">{(user?.name || user?.email || 'U').slice(0, 1).toUpperCase()}</span>
            <span className="account-copy"><strong>{user?.name || 'Your account'}</strong><small>{user?.email}</small></span>
            <ChevronDown size={15} />
          </button>
        </div>
      </aside>

      <section className="main-panel">
        <header className="topbar">
          <div className="breadcrumb">
            <span>Workspace</span>
            <span className="breadcrumb-slash">/</span>
            <strong>{activeTitle ? `${activeTitle.slice(0, 32)}${activeTitle.length > 32 ? '…' : ''}` : 'Assistant'}</strong>
          </div>

          <div className="topbar-actions">
            <span className="model-indicator"><span /> Llama 3.3</span>
            <button className="icon-button settings-trigger" onClick={onOpenSettings} aria-label="Settings" title="Settings"><span>Settings</span><Settings2 size={18} /></button>
          </div>
        </header>

        <div className={`conversation-area ${messages.length ? 'has-messages' : ''}`}>
          {messages.length === 0 ? (
            <div className="welcome-panel">
              <div className="welcome-kicker"><Sparkles size={13} /> A LITTLE SPACE TO THINK</div>
              <h1>Good ideas start<br />with a <em>conversation.</em></h1>
              <p>Ask a question, untangle a thought, or explore something new. We can figure it out together.</p>

              <div className="prompt-grid">
                <button onClick={() => onInputChange('Help me make sense of a big idea I have')}><span className="prompt-symbol symbol-coral"><Sparkles size={16} /></span><span><strong>Explore an idea</strong><small>Turn a thought into a plan</small></span><ArrowUp size={15} className="prompt-arrow" /></button>
                <button onClick={() => onInputChange('Explain something complicated in a simple way')}><span className="prompt-symbol symbol-green"><Command size={16} /></span><span><strong>Learn something</strong><small>Make the complex feel clear</small></span><ArrowUp size={15} className="prompt-arrow" /></button>
                <button onClick={() => onInputChange('Help me write something thoughtful')}><span className="prompt-symbol symbol-yellow"><MessageSquareText size={16} /></span><span><strong>Find the words</strong><small>Write, refine, and make it yours</small></span><ArrowUp size={15} className="prompt-arrow" /></button>
              </div>
            </div>
          ) : (
            <div className="message-thread">
              <div className="thread-date"><Clock3 size={13} /> This conversation</div>

              {messages.map((message) => (
                <article className={`message-row ${message.role}`} key={message.id}>
                  {message.role === 'assistant' && <div className="assistant-avatar"><AudioLines size={16} /></div>}
                  <div className="message-content">
                    {message.role === 'assistant' && <span className="message-author">AI Voice Assistant</span>}
                    <p>{message.content}</p>
                  </div>
                  {message.role === 'user' && <div className="user-avatar">{(user?.name || user?.email || 'U').slice(0, 1).toUpperCase()}</div>}
                </article>
              ))}

              {sending && (
                <div className="message-row assistant">
                  <div className="assistant-avatar"><AudioLines size={16} /></div>
                  <div className="typing-indicator"><i /><i /><i /></div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        <div className="composer-wrap">
          {error && <div className="inline-error" role="alert"><span>{error}</span><button onClick={onClearError} aria-label="Dismiss error"><X size={15} /></button></div>}

          <form className="composer" onSubmit={(event) => { event.preventDefault(); onSendMessage(input) }}>
            <textarea
              value={input}
              onChange={(event) => onInputChange(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  onSendMessage(input)
                }
              }}
              placeholder="Ask anything, or just start somewhere..."
              rows={2}
              aria-label="Your message"
            />

            <div className="composer-footer">
              <div className="composer-hint"><ShieldCheck size={14} /><span>Your conversations are private</span></div>

              <div className="composer-actions">
                <button className={`mic-button ${listening ? 'recording' : ''}`} type="button" onClick={onStartVoiceInput} aria-label={listening ? 'Stop recording' : 'Start voice input'} aria-pressed={listening} title={listening ? 'Stop recording' : 'Speak a message'}><Mic size={17} /></button>
                <button className="send-button" type="submit" disabled={!input.trim() || sending} aria-label="Send message" title="Send message"><ArrowUp size={18} /></button>
              </div>
            </div>
          </form>

          <div className="composer-caption">AI Voice Assistant can make mistakes. Trust your judgment on the important things.</div>
        </div>
      </section>
    </main>
  )
}

export default Chat
