import { useEffect, useRef, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { ApiError, displayDate, errorMessage, request } from './api';

export function StateTag({ state }: { state: string }) {
  const style = ['Approved', 'Verified', 'Connected'].includes(state) ? 'positive' : ['Rejected', 'Suspended', 'Critical', 'Expired'].includes(state) ? 'danger' : ['Missing Evidence', 'Not Connected', 'Requires Domain Review'].includes(state) ? 'warning' : '';
  return <span className={`state ${style}`}><span aria-hidden="true" className="state-dot" />{state}</span>;
}
export function Notice({ children, danger = false }: { children: ReactNode; danger?: boolean }) {
  return <div className={`notice ${danger ? 'error' : ''}`} role={danger ? 'alert' : 'status'}>{children}</div>;
}
export function Empty({ title, children }: { title: string; children: ReactNode }) {
  return <div className="empty"><span className="empty-mark" aria-hidden="true">—</span><h3>{title}</h3><p>{children}</p></div>;
}
export function JsonView({ value }: { value: unknown }) { return <pre className="json-view">{JSON.stringify(value, null, 2)}</pre>; }
export function useRemote<T>(path: string, token: string, revision = 0) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [checkedAt, setCheckedAt] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(''); setData(null);
    request<T>(path, token, { signal: controller.signal }).then(result => { setData(result); setCheckedAt(new Date().toISOString()); }).catch((cause: unknown) => {
      if (!(cause instanceof DOMException && cause.name === 'AbortError')) setError(errorMessage(cause));
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [path, token, revision]);
  return { data, error, loading, checkedAt };
}
export function Updated({ time }: { time: string }) { return <span className="updated">{time ? `Fetched ${displayDate(time)}` : 'Awaiting server response'}</span>; }
export function Panel({ title, close, children }: { title: string; close: () => void; children: ReactNode }) {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { heading.current?.focus(); }, []);
  useEffect(() => { function keydown(event: KeyboardEvent) { if (event.key === 'Escape') close(); } document.addEventListener('keydown', keydown); return () => document.removeEventListener('keydown', keydown); }, [close]);
  return <section className="record-panel" aria-label={title}><div className="panel-heading"><h2 ref={heading} tabIndex={-1}>{title}</h2><button className="icon-button" aria-label="Close record panel" onClick={close}>×</button></div>{children}</section>;
}
export function Login({ onLogin }: { onLogin: (session: import('./api').Session) => void }) {
  const [email, setEmail] = useState(''); const [password, setPassword] = useState('');
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try { onLogin(await request('/session', null, { method: 'POST', body: JSON.stringify({ email, password }) })); }
    catch (cause) { setError(cause instanceof ApiError && cause.status === 401 ? 'The email or password was not accepted.' : errorMessage(cause)); }
    finally { setBusy(false); }
  }
  return <main className="login-shell"><div className="login-brand"><span className="wordmark">SYSTEM LAB</span><span>Airspace Operations</span></div><section className="login-panel"><p className="eyebrow">Organisation access</p><h1>Sign in to your workspace</h1><p className="muted">Operational management and decision support for civilian UAS services.</p>{error ? <Notice danger>{error}</Notice> : null}<form onSubmit={submit}><label>Email<input type="email" autoComplete="username" required value={email} onChange={event => setEmail(event.target.value)} /></label><label>Password<input type="password" autoComplete="current-password" required value={password} onChange={event => setPassword(event.target.value)} /></label><button className="primary" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button></form><p className="small muted">Accounts are provisioned by your administrator. Contact your organisation administrator if you need access.</p></section><footer>Engineering release candidate · Operational deployment requires acceptance and applicable permissions.</footer></main>;
}
