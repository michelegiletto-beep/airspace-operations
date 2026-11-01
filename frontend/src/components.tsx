import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { AgentCompanion } from './AgentCompanion';
import { AmbientBackground } from './AmbientBackground';
import { ApiError, displayDate, errorMessage, request } from './api';

export function StateTag({ state }: { state: string }) {
  const style = ['Approved', 'Verified', 'Connected'].includes(state) ? 'positive' : ['Rejected', 'Suspended', 'Critical', 'Expired','Failed'].includes(state) ? 'danger' : ['Missing Evidence', 'Not Connected', 'Requires Domain Review','Blocked','Needs Review','Reconciliation Required','Incomplete','INCOMPLETE','INFEASIBLE'].includes(state) ? 'warning' : '';
  return <span className={`state ${style}`}><span aria-hidden="true" className="state-dot" />{state}</span>;
}
export function Notice({ children, danger = false }: { children: ReactNode; danger?: boolean }) {
  return <div className={`notice ${danger ? 'error' : ''}`} role={danger ? 'alert' : 'status'}>{children}</div>;
}
export function Empty({ title, children }: { title: string; children: ReactNode }) {
  return <div className="empty"><span className="empty-mark" aria-hidden="true">—</span><h3>{title}</h3><p>{children}</p></div>;
}
export function JsonView({ value }: { value: unknown }) { return <pre className="json-view">{JSON.stringify(value, null, 2)}</pre>; }
export function useRemote<T>(path: string, token: string, revision = 0, contextKey = '') {
  const [attempt, setAttempt] = useState(0);
  type Snapshot = { path: string; token: string; revision: number; attempt: number; contextKey: string;
    data: T | null; error: string; loading: boolean; checkedAt: string };
  const [snapshot, setSnapshot] = useState<Snapshot>(() => ({ path, token, revision, attempt, contextKey,
    data: null, error: '', loading: true, checkedAt: '' }));
  const reload = useCallback(() => setAttempt(value => value + 1), []);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    const scope = { path, token, revision, attempt, contextKey };
    const commit = (next: Snapshot) => {
      if (!active || controller.signal.aborted) return;
      setSnapshot(previous => active && !controller.signal.aborted ? next : previous);
    };
    commit({ ...scope, data: null, error: '', loading: true, checkedAt: '' });
    request<T>(path, token, { signal: controller.signal }).then(data => {
      commit({ ...scope, data, error: '', loading: false, checkedAt: new Date().toISOString() });
    }).catch((cause: unknown) => {
      if (!active || controller.signal.aborted) return;
      commit({ ...scope, data: null, error: errorMessage(cause), loading: false, checkedAt: '' });
    });
    return () => { active = false; controller.abort(); };
  }, [path, token, revision, attempt, contextKey]);
  const current = snapshot.path === path && snapshot.token === token && snapshot.revision === revision
    && snapshot.attempt === attempt && snapshot.contextKey === contextKey;
  return { data: current ? snapshot.data : null, error: current ? snapshot.error : '',
    loading: current ? snapshot.loading : true, checkedAt: current ? snapshot.checkedAt : '', reload };
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
  return <main className="login-shell"><AmbientBackground/><div className="login-brand"><span className="wordmark">SYSTEM LAB</span><span>Airspace Operations</span></div><section className="login-panel"><AgentCompanion label="Sign in to ask for help"/><h1>Sign in to your workspace</h1><p className="muted">Use your organisation account to continue.</p>{error ? <Notice danger>{error}</Notice> : null}<form onSubmit={submit}><label>Email<input type="email" autoComplete="username" required value={email} onChange={event => setEmail(event.target.value)} /></label><label>Password<input type="password" autoComplete="current-password" required value={password} onChange={event => setPassword(event.target.value)} /></label><button className="primary" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button></form><p className="small muted">Your organisation administrator manages access to this workspace.</p></section><footer>Engineering candidate. Operational use requires your organisation’s acceptance and the applicable permissions.</footer></main>;
}
