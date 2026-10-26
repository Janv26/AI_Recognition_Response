import { Check, LogOut, Volume2, X } from 'lucide-react'

function SettingsModal({ open, settings, setSettings, onClose, onSave, onClearSession, saving }) {
  if (!open) return null

  return (
    <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="settings-modal" role="dialog" aria-modal="true" aria-labelledby="settings-title">
        <header>
          <div>
            <span className="modal-eyebrow">YOUR SPACE</span>
            <h2 id="settings-title">Preferences</h2>
          </div>
          <button className="icon-button" aria-label="Close preferences" onClick={onClose}><X size={18} /></button>
        </header>

        <form onSubmit={onSave}>
          <label className="field-label" htmlFor="display-name">Your name</label>
          <input id="display-name" value={settings.name} onChange={(event) => setSettings((current) => ({ ...current, name: event.target.value }))} maxLength={120} />

          <label className="field-label" htmlFor="language-select">Language</label>
          <select id="language-select" value={settings.language} onChange={(event) => setSettings((current) => ({ ...current, language: event.target.value }))}>
            {['English', 'Spanish', 'French', 'Hindi', 'Arabic', 'Japanese', 'Portuguese'].map((language) => (
              <option key={language}>{language}</option>
            ))}
          </select>

          <label className="toggle-row" htmlFor="voice-replies">
            <span className="toggle-icon"><Volume2 size={17} /></span>
            <span className="toggle-copy"><strong>Spoken replies</strong><small>Read voice responses aloud</small></span>
            <input id="voice-replies" type="checkbox" checked={settings.voiceEnabled} onChange={(event) => setSettings((current) => ({ ...current, voiceEnabled: event.target.checked }))} />
            <span className="toggle-track" />
          </label>

          <div className="settings-actions">
            <button type="button" className="signout-button" onClick={onClearSession}><LogOut size={15} /> Sign out</button>
            <button className="save-button" type="submit" disabled={saving}>{saving ? 'Saving…' : <><Check size={15} /> Save changes</>}</button>
          </div>
        </form>
      </section>
    </div>
  )
}

export default SettingsModal
