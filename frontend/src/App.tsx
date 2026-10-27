import { useEffect, useState } from 'react';
import { errorMessage, request } from './api';
import type { Session } from './api';
import { Login, Notice } from './components';
import Records from './Records';
import Library from './Library';
import { EconomicsWorkbench, SiteScreening, SoraWorkbench } from './AnalysisTools';
import { Administration, OperationalBoundary, Scheduling } from './SpecialWorkspaces';
import { kinds, workspaces } from './schema';

const sessionKey = 'sl-airspace-session-v1';
function storedSession(): Session | null { try { const raw = sessionStorage.getItem(sessionKey); const result = raw ? JSON.parse(raw) as Session : null; return result?.token && result.user?.id ? result : null; } catch { return null; } }
function storedWorkspace(): string { const id = location.hash.slice(1); return workspaces.some(workspace => workspace.id === id) ? id : 'operations'; }
export default function App() {
  const [session, setSession] = useState<Session | null>(storedSession);
  const [validating, setValidating] = useState(Boolean(session)); const [sessionError, setSessionError] = useState('');
  const [workspaceId, setWorkspaceId] = useState(storedWorkspace); const [kindId, setKindId] = useState(workspaces.find(workspace => workspace.id === workspaceId)?.kinds[0] ?? '');
  const [revision, setRevision] = useState(0); const [menu, setMenu] = useState(false);
  const workspace = workspaces.find(item => item.id === workspaceId) ?? workspaces[0];
  useEffect(() => {
    if (!session?.token) return;
    const controller = new AbortController();
    request('/me', session.token, { signal: controller.signal }).catch((cause: unknown) => { if (!(cause instanceof DOMException && cause.name === 'AbortError')) { setSessionError(errorMessage(cause)); sessionStorage.removeItem(sessionKey); setSession(null); } }).finally(() => { if (!controller.signal.aborted) setValidating(false); });
    return () => controller.abort();
  }, [session?.token]);
  useEffect(() => { document.title = session ? `${workspace.label} · System Lab Airspace Operations` : 'System Lab Airspace Operations'; }, [workspace.label, session]);
  useEffect(() => { function sync() { const id = storedWorkspace(); setWorkspaceId(id); setKindId(workspaces.find(item => item.id === id)?.kinds[0] ?? ''); } window.addEventListener('hashchange', sync); return () => window.removeEventListener('hashchange', sync); }, []);
  function login(value: Session) { sessionStorage.setItem(sessionKey, JSON.stringify(value)); setSession(value); setSessionError(''); setValidating(false); }
  async function logout() { const token = session?.token; try { if (token) await request('/session', token, { method: 'DELETE' }); } catch { setSessionError('Local session cleared. Server revocation could not be confirmed; contact an administrator if required.'); } finally { for (const key of Object.keys(sessionStorage)) if (key.startsWith('sl-airspace-')) sessionStorage.removeItem(key); setSession(null); } }
  function navigate(id: string) { location.hash = id; setWorkspaceId(id); setKindId(workspaces.find(item => item.id === id)?.kinds[0] ?? ''); setMenu(false); }
  if (!session) return <>{sessionError ? <Notice danger>Session ended: {sessionError}</Notice> : null}<Login onLogin={login} /></>;
  if (validating) return <main className="session-check" role="status">Checking authenticated session…</main>;
  return <div className="app-shell"><a className="skip-link" href="#main-content">Skip to workspace</a><aside className={`sidebar ${menu ? 'mobile-open' : ''}`}><a className="product-identity" href="#operations" onClick={event => { event.preventDefault(); navigate('operations'); }}><span className="wordmark">SYSTEM LAB</span><span>Airspace Operations</span><span className="release-label">Engineering release candidate</span></a><p className="nav-label">WORKSPACES</p><nav aria-label="Primary workspaces">{workspaces.map(item => <button key={item.id} className={workspaceId === item.id ? 'active' : ''} aria-current={workspaceId === item.id ? 'page' : undefined} onClick={() => navigate(item.id)}><span className="nav-code">{item.code}</span><span>{item.label}</span>{workspaceId === item.id ? <span aria-hidden="true" className="nav-active-dot" /> : null}</button>)}</nav><div className="sidebar-bottom"><div className="boundary-label"><span className="boundary-square" aria-hidden="true" /><span>Decision-support platform</span></div><p>Software verification does not grant authority approval or operational acceptance.</p><a href="/api/docs" target="_blank" rel="noreferrer">API documentation ↗</a></div></aside><div className="app-main"><header className="topbar"><div className="breadcrumb"><button className="mobile-menu icon-button" onClick={() => setMenu(value => !value)} aria-expanded={menu} aria-label="Toggle workspaces">☰</button><span>Organisation workspace</span><span aria-hidden="true">/</span><strong>{workspace.label}</strong></div><div className="account"><span className="account-role">{session.user.role}</span><span className="account-email" title={session.user.email}>{session.user.email}</span><button onClick={logout}>Sign out</button></div></header><main id="main-content" tabIndex={-1}><div className="workspace-heading"><div><p className="eyebrow">WORKSPACE {workspace.code}</p><h1>{workspace.label}</h1><p className="workspace-description">{workspace.description}</p></div><div className="workspace-meta"><span className="environment-tag">AUTHENTICATED WORKSPACE</span><span>Organisation <code title={session.user.organisation_id}>{session.user.organisation_id.slice(0, 12)}</code></span></div></div>
    {workspace.id === 'operations' ? <OperationalBoundary /> : null}
    {workspace.id === 'airspace' ? <Notice>Spatial records require authoritative data, explicit vertical references and validated constraints. Routes remain proposals until separately reviewed and approved.</Notice> : null}
    {workspace.id === 'incidents' ? <Notice>Use approved operator procedures. The platform does not issue aircraft commands or automatically contact emergency services.</Notice> : null}
    {workspace.id === 'commercial' ? <Notice>Documented facts and analyst assumptions must remain distinguishable. Commercial scores cannot override a safety or permission blocker.</Notice> : null}
    {workspace.id === 'scheduling' ? <Scheduling token={session.token} role={session.user.role} revision={revision} /> : null}
    {workspace.id === 'airspace' ? <SiteScreening token={session.token} /> : null}
    {workspace.id === 'safety' ? <SoraWorkbench token={session.token} /> : null}
    {workspace.id === 'commercial' ? <EconomicsWorkbench token={session.token} /> : null}
    {workspace.kinds.length > 0 ? <><div className="subnav" role="tablist" aria-label={`${workspace.label} record categories`}>{workspace.kinds.map(id => <button role="tab" aria-selected={kindId === id} key={id} onClick={() => setKindId(id)}>{kinds[id].label}</button>)}</div><Records key={`${workspace.id}-${kindId}`} kindId={kindId || workspace.kinds[0]} token={session.token} user={session.user} revision={revision} changed={() => setRevision(value => value + 1)} /></> : workspace.id === 'library' ? <Library token={session.token} revision={revision} /> : <Administration token={session.token} revision={revision} />}
    <footer className="workspace-footer"><span>All timestamps are UTC unless explicitly labelled. Missing data remains missing.</span><span>System Lab · 0.1.0-rc.1</span></footer></main></div></div>;
}


