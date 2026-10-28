import { useEffect,useState } from 'react';
import { errorMessage,request } from './api';
import type { Session } from './api';
import { Login,Notice } from './components';
import Records from './Records';
import Library from './Library';
import { EconomicsWorkbench,SoraWorkbench } from './AnalysisTools';
import { Administration } from './SpecialWorkspaces';
import { MissionDesk } from './MissionDesk';
import { AirspaceDesk } from './AirspaceDesk';
import { AgentWorkspace } from './AgentWorkspace';
import { FleetDesk } from './FleetDesk';
import { CoordinationDesk } from './CoordinationDesk';
import { SchedulingDesk } from './SchedulingDesk';
import { AgentCompanion } from './AgentCompanion';
import { Icon } from './Icons';
import { kinds,workspaces } from './schema';
import { releaseVersion } from './release';
const sessionKey='sl-airspace-session-v1';
function storedSession():Session|null{try{const raw=sessionStorage.getItem(sessionKey);const result=raw?JSON.parse(raw) as Session:null;return result?.token&&result.user?.id?result:null;}catch{return null;}}
function storedWorkspace():string{const id=location.hash.slice(1);return workspaces.some(workspace=>workspace.id===id)?id:'operations';}
export default function App(){
 const [session,setSession]=useState<Session|null>(storedSession);const [validating,setValidating]=useState(Boolean(session));const [sessionError,setSessionError]=useState('');
 const [workspaceId,setWorkspaceId]=useState(storedWorkspace);const [kindId,setKindId]=useState(workspaces.find(workspace=>workspace.id===workspaceId)?.kinds[0]??'');const [revision,setRevision]=useState(0);const [menu,setMenu]=useState(false);
 const workspace=workspaces.find(item=>item.id===workspaceId)??workspaces[0];
 useEffect(()=>{if(!session?.token)return;const controller=new AbortController();request('/me',session.token,{signal:controller.signal}).catch((cause:unknown)=>{if(!(cause instanceof DOMException&&cause.name==='AbortError')){setSessionError(errorMessage(cause));sessionStorage.removeItem(sessionKey);setSession(null);}}).finally(()=>{if(!controller.signal.aborted)setValidating(false);});return()=>controller.abort();},[session?.token]);
 useEffect(()=>{document.title=session?`${workspace.label} · System Lab Airspace Operations`:'System Lab Airspace Operations';},[workspace.label,session]);
 useEffect(()=>{function sync(){const id=storedWorkspace();setWorkspaceId(id);setKindId(workspaces.find(item=>item.id===id)?.kinds[0]??'');}window.addEventListener('hashchange',sync);return()=>window.removeEventListener('hashchange',sync);},[]);
 function login(value:Session){sessionStorage.setItem(sessionKey,JSON.stringify(value));setSession(value);setSessionError('');setValidating(false);}
 async function logout(){const token=session?.token;try{if(token)await request('/session',token,{method:'DELETE'});}catch{setSessionError('Local session cleared. Server revocation could not be confirmed.');}finally{for(const key of Object.keys(sessionStorage))if(key.startsWith('sl-airspace-'))sessionStorage.removeItem(key);setSession(null);}}
 function navigate(id:string){location.hash=id;setWorkspaceId(id);setKindId(workspaces.find(item=>item.id===id)?.kinds[0]??'');setMenu(false);}
 if(!session)return <>{sessionError?<Notice danger>Session ended: {sessionError}</Notice>:null}<Login onLogin={login}/></>;
 if(validating)return <main className="session-check" role="status">Checking authenticated workspace…</main>;
 const props={token:session.token,user:session.user,revision,changed:()=>setRevision(value=>value+1),navigate};
 const bespoke=['operations','airspace','agents','fleet','crossborder','scheduling'].includes(workspaceId);
 const navGroups=[{label:'OPERATIONS',ids:['operations','scheduling','airspace','crossborder','fleet']},{label:'ASSURANCE',ids:['authorisations','safety','library','incidents']},{label:'COORDINATION',ids:['agents','commercial','administration']}];
 return <div className="app-shell"><a className="skip-link" href="#main-content">Skip to workspace</a><aside className={`sidebar ${menu?'mobile-open':''}`}><a className="product-identity" href="#operations" onClick={event=>{event.preventDefault();navigate('operations');}}><span className="wordmark">SYSTEM LAB</span><strong>Airspace Operations</strong><span className="release-label">ENGINEERING CANDIDATE <i>{releaseVersion}</i></span></a><nav aria-label="Primary workspaces">{navGroups.map(group=><div className="nav-group" key={group.label}><p className="nav-label">{group.label}</p>{group.ids.map(id=>{const item=workspaces.find(entry=>entry.id===id)!;return <button key={id} className={workspaceId===id?'active':''} aria-current={workspaceId===id?'page':undefined} onClick={()=>navigate(id)}><Icon name={id} size={18}/><span>{item.label}</span>{workspaceId===id?<span className="nav-active-dot"/>:null}</button>;})}</div>)}</nav><div className="sidebar-bottom"><button className="sidebar-companion-button" onClick={()=>navigate('agents')}><AgentCompanion compact label="Workflow coordination"/><Icon name="chevron" size={13}/></button><div className="sidebar-platform-link"><Icon name="link" size={13}/><a href="https://giletto-systems-lab.michele-giletto.chatgpt.site/projects/multiagentic-systems" target="_blank" rel="noreferrer">System Lab multiagentic systems</a></div></div></aside><div className="app-main"><header className="topbar"><div className="breadcrumb"><button className="mobile-menu icon-button" onClick={()=>setMenu(value=>!value)} aria-expanded={menu} aria-label="Toggle workspaces"><Icon name="menu" size={18}/></button><span>Organisation workspace</span><span>/</span><strong>{workspace.label}</strong></div><div className="account"><span className="time-standard"><Icon name="clock" size={13}/>UTC</span><span className="account-role">{session.user.role.replaceAll('_',' ')}</span><span className="account-avatar" aria-hidden="true">{session.user.email[0]?.toUpperCase()}</span><span className="account-email" title={session.user.email}>{session.user.email}</span><button onClick={logout}>Sign out</button></div></header><main id="main-content" tabIndex={-1}><div className="workspace-heading"><div><p className="eyebrow">AIRSPACE OPERATIONS / {workspace.code}</p><h1>{workspace.label}</h1><p className="workspace-description">{workspace.description}</p></div><div className="workspace-meta"><span className="environment-tag"><span/>Authenticated workspace</span><span>Organisation <code title={session.user.organisation_id}>{session.user.organisation_id.slice(0,12)}</code></span></div></div>
 {workspaceId==='operations'?<MissionDesk {...props}/>:workspaceId==='airspace'?<AirspaceDesk {...props}/>:workspaceId==='agents'?<AgentWorkspace {...props}/>:workspaceId==='fleet'?<FleetDesk {...props}/>:workspaceId==='crossborder'?<CoordinationDesk {...props}/>:workspaceId==='scheduling'?<SchedulingDesk {...props}/>:null}
 {!bespoke?<>{workspaceId==='incidents'?<Notice>Approved operator procedures govern response. Source receipts, acknowledgements and completed actions remain distinct.</Notice>:null}{workspaceId==='commercial'?<EconomicsWorkbench token={session.token}/>:null}{workspaceId==='safety'?<SoraWorkbench token={session.token}/>:null}{workspace.kinds.length?<><div className="subnav" role="tablist" aria-label={`${workspace.label} record categories`}>{workspace.kinds.map(id=><button role="tab" aria-selected={kindId===id} key={id} onClick={()=>setKindId(id)}><Icon name={id==='case'?'authorisations':id==='evidence'?'document':id==='permission'?'lock':'document'} size={15}/>{kinds[id].label}</button>)}</div><Records key={`${workspace.id}-${kindId}`} kindId={kindId||workspace.kinds[0]} token={session.token} user={session.user} revision={revision} changed={props.changed}/></>:workspaceId==='library'?<Library token={session.token} revision={revision}/>:<Administration token={session.token} revision={revision}/>}</>:null}
 <footer className="workspace-footer"><span><Icon name="lock" size={11}/>Decision support · Authority instruments, internal readiness and actual execution remain separate.</span><span>System Lab · {releaseVersion} · UTC timestamps</span></footer></main></div></div>;
}
