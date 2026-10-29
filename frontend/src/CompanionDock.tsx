import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { displayDate, errorMessage, request } from './api';
import type { Collection, DomainRecord, User } from './api';
import { AgentCompanion } from './AgentCompanion';
import { CompanionNextSteps } from './CompanionNextSteps';
import { CompanionArtwork } from './CompanionArtwork';
import type { CompanionGesture } from './CompanionArtwork';
import { companionWorkspaces } from './companionApi';
import type { ActionPreview, CompanionCatalog, CompanionConversation, CompanionDetail, CompanionTask, ConfirmResponse, SendResponse } from './companionApi';
import { JsonView, Notice, StateTag, useRemote } from './components';
import { Icon } from './Icons';
import { useCompanionMotion } from './useCompanionMotion';
import { useDraftState } from './useDraft';

const activeStates = ['Queued', 'Running'];
function actionState(action: ActionPreview, clock: number) {
  if (action.status !== 'Awaiting Confirmation') return action.status;
  const expiry = Date.parse(action.data.expires_at ?? '');
  return !Number.isFinite(expiry) ? 'Validity unknown' : expiry <= clock ? 'Expired' : action.status;
}
const prompts: Record<string, string[]> = {
  operations: ['Help me plan an intended operation.', 'What information do I need before scheduling a mission?'],
  fleet: ['Help me review maintenance for a saved aircraft.', 'Help me organise the maintenance tasks that are still open.'],
  airspace: ['Help me assess a saved site or route.', 'Explain which geographical and altitude references I need.'],
  crossborder: ['Help me check the requirements for a cross-border operation.', 'What information do you need for each country segment?'],
  library: ['Help me research the rules for my intended operation.', 'Explain how to check the date and jurisdiction of a source.'],
  authorisations: ['Help me prepare an authorisation case.', 'Help me list the evidence that is still missing.'],
  scheduling: ['Help me prepare a scheduling proposal.', 'Explain what is blocking a saved scheduling proposal.'],
};

export function CompanionDock({ token, user, workspace, workspaceLabel, revision, changed, open, onOpenChange, openWorkflow, openWorkspace }: {
  token: string; user: User; workspace: string; workspaceLabel: string; revision: number;
  changed: () => void; open: boolean; onOpenChange: (open: boolean) => void; openWorkflow: (id: string) => void;
  openWorkspace?: (id: string) => void;
}) {
  const prefix = `sl-airspace-companion-draft:${user.organisation_id}:${user.id}`;
  const [tab, setTab] = useState<'conversation' | 'tasks'>('conversation');
  const [conversationId, setConversationId] = useDraftState(`${prefix}:conversation-id`, '');
  const [storedDetail,setDetail]=useState<CompanionDetail|null>(null);
  const detail=storedDetail?.conversation.id===conversationId?storedDetail:null;
  const [localRevision, setLocalRevision] = useState(0);
  const [detailRevision, setDetailRevision] = useState(0);
  const [detailUnavailable, setDetailUnavailable] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [taskBusy, setTaskBusy] = useState('');
  const [contextRecords, setContextRecords] = useState<DomainRecord[]>([]);
  const [contextError, setContextError] = useState('');
  const [contextIds, setContextIds] = useState<string[]>([]);
  const [createdCase,setCreatedCase]=useState<{conversationId:string;record:DomainRecord}|null>(null);
  const [createdTask,setCreatedTask]=useState<{conversationId:string;record:CompanionTask}|null>(null);
  const [clock,setClock]=useState(Date.now);
  const [message, setMessage] = useDraftState(`${prefix}:message`, '');
  const [jurisdiction, setJurisdiction] = useDraftState(`${prefix}:jurisdiction`, '');
  const [operationDate, setOperationDate] = useDraftState(`${prefix}:operation-date`, '');
  const [gesture, setGesture] = useState<CompanionGesture>({ name: 'soft', sequence: 0 });
  const heading = useRef<HTMLHeadingElement>(null);
  const launcher = useRef<HTMLButtonElement>(null);
  const history = useRef<HTMLDivElement>(null);
  const wasOpen = useRef(false);
  const { motion } = useCompanionMotion();
  const catalogue = useRemote<CompanionCatalog>('/companion/catalog', token, revision);
  const conversations = useRemote<Collection<CompanionConversation>>('/companion/conversations', token, localRevision);
  const taskList = useRemote<Collection<CompanionTask>>('/companion/tasks', token, revision + localRevision);
  const refresh = () => { setDetailUnavailable(false); setLocalRevision(value => value + 1); changed(); };
  const animate = (name: CompanionGesture['name']) => setGesture(previous => ({ name, sequence: previous.sequence + 1 }));

  useEffect(() => {
    if (open) heading.current?.focus();
    else if (wasOpen.current) launcher.current?.focus();
    wasOpen.current = open;
  }, [open]);

  useEffect(() => {
    if (!conversationId) { setDetail(null); return; }
    const controller = new AbortController();
    setDetail(previous => previous?.conversation.id === conversationId ? previous : null);
    request<CompanionDetail>(`/companion/conversations/${encodeURIComponent(conversationId)}`, token, { signal: controller.signal })
      .then(value => { if (!controller.signal.aborted) { setDetailUnavailable(false); setDetail(previous => previous?.conversation.id === value.conversation.id && previous.conversation.version > value.conversation.version ? previous : value); } })
      .catch(cause => { if (!controller.signal.aborted) { setDetailUnavailable(true); setError(errorMessage(cause)); } });
    return () => controller.abort();
  }, [conversationId, token, localRevision, detailRevision]);

  useEffect(() => { setCreatedCase(null); setCreatedTask(null); }, [conversationId]);

  useEffect(() => {
    const future=(detail?.action_previews??[]).filter(action=>action.status==='Awaiting Confirmation').map(action=>Date.parse(action.data.expires_at??'')).filter(time=>Number.isFinite(time)&&time>clock);
    if(!future.length)return;
    const timer=window.setTimeout(()=>setClock(Date.now()),Math.min(2_147_000_000,Math.max(0,Math.min(...future)-Date.now()+5)));
    return()=>window.clearTimeout(timer);
  },[detail?.action_previews,clock]);

  const activeJob = Boolean(detail?.active_job && activeStates.includes(detail.active_job.state));
  useEffect(() => {
    if (!conversationId || !activeJob || detailUnavailable) return;
    const timer = window.setInterval(() => setDetailRevision(value => value + 1), 1800);
    return () => window.clearInterval(timer);
  }, [conversationId, activeJob, detailUnavailable]);

  useEffect(() => {
    if (open && history.current) history.current.scrollTop = history.current.scrollHeight;
  }, [open, detail?.messages.length, detail?.action_previews.length]);

  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    Promise.all(['case', 'mission', 'site', 'route', 'aircraft'].map(async kind => {
      const result = await request<Collection<DomainRecord>>(`/records/${kind}`, token, { signal: controller.signal });
      return result.items;
    })).then(values => { if (!controller.signal.aborted) { setContextRecords(values.flat()); setContextError(''); } })
      .catch(cause => { if (!controller.signal.aborted) setContextError(errorMessage(cause)); });
    return () => controller.abort();
  }, [open, token, revision]);

  const model = detail?.model_status ?? catalogue.data?.model_status;
  const waitingReview = detail?.action_previews.some(action => actionState(action,clock) === 'Awaiting Confirmation');
  const state = detailUnavailable ? 'attention' : detail?.active_job?.state === 'Running' || busy ? 'running' : model?.state==='Procedure Required'?'attention': waitingReview ? 'attention' : model && ['Not Installed', 'Unavailable', 'Rejected Output', 'Budget Exhausted', 'Budget Unavailable'].includes(model.state) ? 'unavailable' : 'idle';
  const tasks = taskList.data?.items ?? [];
  const openTasks = tasks.filter(task => !['Completed', 'Cancelled'].includes(task.status));
  const conversationWorkspace = detail?.conversation.data.workspace;

  async function send(event: FormEvent) {
    event.preventDefault();
    await submitMessage(message.trim());
  }

  async function submitMessage(text: string, previousMessage?: import('./companionApi').CompanionMessage) {
    if (!text || busy || activeJob) return;
    setBusy(true); setError(''); animate('send');
    try {
      let conversation = detail?.conversation;
      if (conversationId && (!conversation || conversation.id!==conversationId)) throw new Error('Wait for the selected conversation to load, or start a new conversation.');
      if (!conversation) {
        conversation = await request<CompanionConversation>('/companion/conversations', token, {
          method: 'POST', body: JSON.stringify({ workspace: companionWorkspaces[workspace] ?? 'operations', context_record_ids: contextIds }),
        });
        setConversationId(conversation.id);
      }
      const result = await request<SendResponse>(`/companion/conversations/${conversation.id}/messages`, token, {
        method: 'POST', body: JSON.stringify({ message: text, expected_version: conversation.version,
          ...((previousMessage ? previousMessage.data.request?.jurisdiction : jurisdiction) ? { jurisdiction: previousMessage ? previousMessage.data.request?.jurisdiction : jurisdiction } : {}),
          ...((previousMessage ? previousMessage.data.request?.operation_date : operationDate) ? { operation_date: previousMessage ? previousMessage.data.request?.operation_date : operationDate } : {}) }),
      });
      setDetail(previous => ({ conversation: result.conversation, messages: [...(previous?.conversation.id === result.conversation.id ? previous.messages : []), result.user_message], action_previews: previous?.conversation.id === result.conversation.id ? previous.action_previews : [], tasks: previous?.conversation.id === result.conversation.id ? previous.tasks : [], active_job: result.job, model_status: result.model_status }));
      if (!previousMessage) setMessage('');
      refresh();
    } catch (cause) { setError(errorMessage(cause)); animate('uncertain'); }
    finally { setBusy(false); }
  }

  async function decide(action: ActionPreview, decision: 'confirm' | 'reject') {
    if (!detail || busy) return;
    setBusy(true); setError('');
    try {
      const result = await request<ConfirmResponse>(`/companion/conversations/${detail.conversation.id}/actions/${action.id}/${decision}`, token, {
        method: 'POST', body: JSON.stringify({ expected_version: detail.conversation.version, expected_action_version: action.version }),
      });
      setDetail(previous => previous?.conversation.id === result.conversation.id ? { ...previous, conversation: result.conversation, action_previews: previous.action_previews.map(item => item.id === result.action.id ? result.action : item) } : previous);
      if (result.workflow) setWorkflowSelection({conversationId:result.conversation.id,id:result.workflow.id});
      if (result.case) setCreatedCase({conversationId:result.conversation.id,record:result.case});
      if (result.task) setCreatedTask({conversationId:result.conversation.id,record:result.task});
      animate(decision === 'confirm' ? 'ack' : 'settle'); refresh();
    } catch (cause) { setError(errorMessage(cause)); animate('uncertain'); }
    finally { setBusy(false); }
  }

  async function cancelReply() {
    if (!detail || !activeJob || busy) return;
    setBusy(true); setError('');
    try {
      const result = await request<{conversation: CompanionConversation}>(`/companion/conversations/${detail.conversation.id}/cancel`, token, {
        method: 'POST', body: JSON.stringify({ expected_version: detail.conversation.version }),
      });
      setDetail(previous => previous?.conversation.id === result.conversation.id ? { ...previous, conversation: result.conversation, active_job: null } : previous);
      animate('settle'); refresh();
    } catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(false); }
  }

  async function updateTask(task: CompanionTask, next: string) {
    setTaskBusy(task.id); setError('');
    try {
      await request(`/companion/tasks/${task.id}`, token, { method: 'PUT', body: JSON.stringify({ expected_version: task.version, state: next }) });
      animate(next === 'Completed' ? 'ack' : 'soft'); refresh();
    } catch (cause) { setError(errorMessage(cause)); }
    finally { setTaskBusy(''); }
  }

  const [workflowSelection,setWorkflowSelection]=useState<{conversationId:string;id:string}|null>(null);
  const workflowId=workflowSelection?.conversationId===conversationId?workflowSelection.id:'';
  const [workflow, setWorkflow] = useState<DomainRecord | null>(null);
  useEffect(() => {
    if (!workflowId) { setWorkflow(null); return; }
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const value = await request<DomainRecord>(`/agent-workflows/${workflowId}`, token, { signal: controller.signal });
        if (controller.signal.aborted) return;
        setWorkflow(value);
        if (activeStates.includes(value.status)) timer = setTimeout(() => void load(), 2000);
      } catch (cause) { if (!controller.signal.aborted) setError(errorMessage(cause)); }
    }
    void load();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [workflowId, token, localRevision]);

  async function controlWorkflow(action: 'advance' | 'pause' | 'resume' | 'cancel') {
    if (!workflow || busy) return;
    setBusy(true); setError('');
    try {
      await request(`/agent-workflows/${workflow.id}/${action === 'advance' ? 'advance' : 'control'}`, token, {
        method: 'POST', body: JSON.stringify({ expected_version: workflow.version, ...(action === 'advance' ? {} : { action }) }),
      });
      refresh();
    } catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(false); }
  }

  return <>
    <button ref={launcher} className={`companion-launcher ${open ? 'dock-is-open' : ''}`} aria-label={open ? 'Close Indigo assistant' : 'Open Indigo assistant'} aria-expanded={open} aria-controls="companion-dock" onClick={() => onOpenChange(!open)}>
      <span className="launcher-art"><CompanionArtwork state={state} appearance="indigo" motion={motion} gesture={gesture}/></span><span><strong>Indigo</strong><small>{detailUnavailable ? 'Status unavailable' : activeJob ? detail?.active_job?.state === 'Queued' ? 'Waiting for the worker' : 'Working on your request' : openTasks.length ? `${openTasks.length} open task${openTasks.length === 1 ? '' : 's'}` : 'Ask for help'}</small></span><Icon name={open ? 'chevron' : 'agents'} size={17}/>
    </button>
    {open ? <aside id="companion-dock" className="companion-dock" aria-label="Indigo assistant" onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); onOpenChange(false); } }}>
      <header className="companion-dock-header"><div><h2 ref={heading} tabIndex={-1}>Ask Indigo</h2><p>Help with {workspaceLabel.toLowerCase()}</p></div><button className="icon-button" aria-label="Close assistant panel" onClick={() => onOpenChange(false)}>×</button></header>
      <AgentCompanion state={state} label={detailUnavailable ? 'Connection lost. Reload to check the request.' : busy ? 'Saving your request' : activeJob ? detail?.active_job?.state === 'Queued' ? 'Waiting for the worker' : detail?.conversation.data.progress?.message ?? 'Processing your request' : model?.state==='Procedure Required'?'Approved procedure required':waitingReview ? 'Please review the proposed action' : 'How can I help?'} gesture={gesture}/>
      <div className="companion-model-status"><span>{model?.state==='Procedure Required'?'Approved procedure required':<>{detail?'Last response model status':'Local model files'}{detailUnavailable?' (last reported)':''}: {model?.state ?? 'Checking'}</>}</span>{model?.message ? <p>{model.message}</p> : null}{catalogue.error ? <p role="alert">{catalogue.error}</p> : null}</div>
      <div className="companion-tabs" role="tablist" aria-label="Assistant views"><button role="tab" disabled={busy} aria-selected={tab === 'conversation'} onClick={() => setTab('conversation')}>Conversation</button><button role="tab" disabled={busy} aria-selected={tab === 'tasks'} onClick={() => setTab('tasks')}>Tasks{openTasks.length ? ` (${openTasks.length})` : ''}</button></div>
      {error ? <div className="companion-error"><Notice danger>{error}</Notice><button className="text-button" onClick={() => { setError(''); refresh(); }}>Reload saved state</button></div> : null}
      {tab === 'conversation' ? <>
        <div className="companion-conversation-picker"><label><span className="sr-only">Saved conversation</span><select value={conversationId} onChange={event => { setConversationId(event.target.value);setJurisdiction('');setOperationDate(''); setError(''); }} disabled={busy}><option value="">New conversation</option>{(conversations.data?.items ?? []).map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label><button className="secondary" onClick={() => { setConversationId(''); setDetail(null); setContextIds([]); setJurisdiction(''); setOperationDate(''); setError(''); }} disabled={busy}>New</button></div>
        {conversations.error ? <Notice danger>{conversations.error}</Notice> : null}
        {conversationWorkspace && conversationWorkspace !== (companionWorkspaces[workspace] ?? 'operations') ? <p className="companion-context-note">This conversation uses its saved {conversationWorkspace.replaceAll('_', ' ')} context. Start a new conversation to use {workspaceLabel.toLowerCase()}.</p> : null}
        <div ref={history} className="companion-history" role="log" aria-label="Conversation messages" aria-live="polite" aria-relevant="additions text">
          {conversationId&&!detail?<p role="status">{detailUnavailable?'Conversation unavailable. Reload to try again.':'Loading saved conversation…'}</p>:!detail?.messages.length ? <div className="companion-welcome"><h3>What would you like to do?</h3><p>Describe the operation or task in your own words. I can help identify missing information and prepare work for you to review.</p>{(prompts[workspace] ?? ['Help me understand the next steps in this workspace.', 'Help me organise my open tasks.']).map(prompt => <button key={prompt} disabled={busy} onClick={() => { setMessage(prompt); animate('question'); }}>{prompt}<Icon name="arrow" size={13}/></button>)}</div> : detail.messages.map(item => <article key={item.id} className={`companion-message message-${item.data.role}`}><header><strong>{item.data.role === 'user' ? 'You' : 'Indigo'}</strong><small>{item.data.reply_kind === 'fallback' ? 'Basic guidance without a model response' : item.data.reply_kind === 'local_llm' ? 'Local model response' : item.data.reply_kind==='procedure_guidance'?'Approved procedure required':displayDate(item.created_at)}</small></header><p>{item.data.text}</p>{item.data.missing_inputs?.length ? <div className="companion-missing"><strong>Information still needed</strong><ul>{item.data.missing_inputs.map((input, index) => <li key={index}>{input}</li>)}</ul></div> : null}<CompanionNextSteps text={item.data.text} steps={item.data.next_steps}/>{item.data.source_refs?.length ? <details><summary>Sources used in this response</summary><JsonView value={item.data.source_refs}/></details> : null}{item.data.model && Object.keys(item.data.model).length ? <details><summary>Model and response details</summary><JsonView value={item.data.model}/></details> : null}{item.data.reply_kind==='procedure_guidance'?<button className="text-button companion-retry" disabled={!openWorkspace} onClick={()=>openWorkspace?.('incidents')}>Open incidents<Icon name="arrow" size={13}/></button>:null}{item.data.reply_kind==='fallback'&&!activeJob&&detail.messages.some(message=>message.id===item.data.reply_to_message_id)?<button className="text-button companion-retry" disabled={busy} onClick={()=>{const original=detail.messages.find(message=>message.id===item.data.reply_to_message_id);if(original)void submitMessage(original.data.text,original);}}>Retry this request</button>:null}</article>)}
          {activeJob ? <div className="companion-job" role="status"><span className="job-indicator"/><div><strong>{detail?.active_job?.state === 'Queued' ? 'Request queued' : 'Processing your request'}</strong><p>{detail?.conversation.data.progress?.message ?? 'Waiting for a saved response from the worker.'}</p>{detail?.conversation.data.progress?.since?<small>Updated {displayDate(detail.conversation.data.progress.since)}</small>:null}<button className="text-button" onClick={() => void cancelReply()} disabled={busy}>Cancel request</button><small>Closing this panel keeps the request running.</small></div></div> : detail?.active_job?.error ? <Notice danger>{detail.active_job.error}</Notice> : null}{!activeJob&&detail?.conversation.data.progress&&['Failed','Cancelled','Expired','Model unavailable'].includes(detail.conversation.data.progress.phase)?<div className="companion-progress-note" role="status"><p>{detail.conversation.data.progress.message}</p>{['Failed','Expired'].includes(detail.conversation.data.progress.phase)?<button className="text-button" disabled={busy} onClick={()=>{const original=[...detail.messages].reverse().find(item=>item.data.role==='user');if(original)void submitMessage(original.data.text,original);}}>Retry last request</button>:null}</div>:null}
          {detail?.action_previews.map(action => <article className="companion-action-preview" key={action.id}><header><strong>{action.data.label}</strong><StateTag state={actionState(action,clock)}/></header><p>{action.data.kind === 'task_draft' ? 'This adds a task to your saved task list.' : action.data.kind === 'case_draft' ? 'This creates a draft authorisation case for you to complete.' : action.data.kind==='workflow_draft' ? 'Confirmation starts this internal workflow and adds a tracking task. Its results require independent review.' : 'This action is unavailable.'}</p>{actionState(action,clock)==='Expired'?<p>This proposal expired. Send a new request for a current preview.</p>:actionState(action,clock)==='Validity unknown'?<p>Proposal validity is unavailable. Reload before continuing.</p>:null}{['case_draft','workflow_draft'].includes(action.data.kind)?<p className="companion-action-visibility">{action.data.kind==='case_draft'?'This draft case will be visible to your organisation.':'This workflow and its results will be visible to your organisation.'}</p>:null}<ActionSummary action={action}/>{typeof action.data.preview.effect==='string'?<p className="companion-action-effect">{action.data.preview.effect}</p>:null}<details><summary>Inspect the complete proposed action</summary><JsonView value={action.data.preview}/></details>{action.status === 'Awaiting Confirmation' ? <div className="companion-preview-buttons"><button className="primary" disabled={busy || actionState(action,clock)!=='Awaiting Confirmation' || action.data.owner_actor_id !== user.id || !['task_draft', 'workflow_draft', 'case_draft'].includes(action.data.kind)} onClick={() => void decide(action, 'confirm')}>{action.data.kind==='workflow_draft'?'Confirm and start workflow':action.data.kind==='case_draft'?'Confirm and create case':action.data.kind==='task_draft'?'Confirm and save task':'Unsupported action'}</button><button className="secondary" disabled={busy || action.data.owner_actor_id !== user.id} onClick={() => void decide(action, 'reject')}>Dismiss</button></div> : null}</article>)}
          {createdCase?.conversationId===conversationId?<article className="companion-created-record"><h3>Draft case saved</h3><p>{createdCase.record.title}</p><p>Complete its details and evidence before requesting review.</p><button className="text-button" disabled={!openWorkspace} onClick={()=>openWorkspace?.('authorisations')}>Open authorisation cases<Icon name="arrow" size={13}/></button></article>:null}{createdTask?.conversationId===conversationId?<article className="companion-created-record"><h3>Task saved</h3><p>{createdTask.record.title}</p><button className="text-button" onClick={()=>setTab('tasks')}>View saved tasks<Icon name="arrow" size={13}/></button></article>:null}
          {workflow ? <WorkflowProgress workflow={workflow} busy={busy} control={controlWorkflow} open={() => openWorkflow(workflow.id)}/> : null}
        </div>
        <form onSubmit={send} className="companion-composer"><label htmlFor="companion-message">Your request</label><textarea id="companion-message" value={message} onChange={event => setMessage(event.target.value)} required maxLength={2000} rows={3} placeholder="Tell me what you want to work on." disabled={busy || activeJob}/><details><summary>Operation date, country and saved records</summary><div className="field-grid"><label>Country code or EU<input maxLength={2} value={jurisdiction} onChange={event => setJurisdiction(event.target.value.toUpperCase())} placeholder="Choose if relevant"/></label><label>Operation date<input type="date" value={operationDate} onChange={event => setOperationDate(event.target.value)}/></label></div>{conversationId ? <p>Each request saves the current versions of the records in this conversation.</p> : <fieldset><legend>Records to include</legend>{contextError ? <Notice danger>{contextError}</Notice> : contextRecords.length ? contextRecords.map(record => <label className="checkbox-row" key={record.id}><input type="checkbox" checked={contextIds.includes(record.id)} disabled={contextIds.length >= 10 && !contextIds.includes(record.id)} onChange={event => setContextIds(previous => event.target.checked ? [...previous, record.id] : previous.filter(id => id !== record.id))}/><span>{record.title}<small>{record.kind} · revision {record.version}</small></span></label>) : <p>No records are available to attach. You can ask a general question or create a proposed operation first.</p>}</fieldset>}</details><div><small>Drafts need your confirmation. Approvals and external actions are unavailable here.</small><button className="primary" disabled={busy || activeJob || !message.trim() || Boolean(conversationId&&!detail)}>{busy ? 'Saving…' : 'Send'}<Icon name="arrow" size={13}/></button></div></form>
      </> : <div className="companion-task-list">{taskList.error ? <Notice danger>{taskList.error}</Notice> : null}{taskList.loading && !tasks.length ? <p role="status">Loading saved tasks…</p> : !tasks.length ? <div className="companion-welcome"><h3>No saved tasks</h3><p>Ask Indigo to help organise work. A proposed task appears in the conversation for your confirmation before it is saved here.</p><button onClick={() => setTab('conversation')}>Return to conversation<Icon name="arrow" size={13}/></button></div> : tasks.map(task => <article key={task.id}><h3>{task.title}</h3><p>{task.data.description}</p><label>{task.data.workflow_id?'Tracking task state':'Task state'}<select aria-label={`${task.data.workflow_id?'Tracking task state':'Task state'} for ${task.title}`} value={task.status} disabled={taskBusy === task.id} onChange={event => void updateTask(task, event.target.value)}>{['Open', 'In Progress', 'Completed', 'Cancelled'].map(status => <option key={status}>{status}</option>)}</select></label>{task.data.workflow_id?<p className="small muted">This changes your tracking task only. Use the workflow controls to pause or cancel the workflow.</p>:null}<small>Updated {displayDate(task.updated_at)}</small><button className="text-button" disabled={busy} onClick={() => { if(task.data.conversation_id!==conversationId){setJurisdiction('');setOperationDate('');}setConversationId(task.data.conversation_id); setTab('conversation'); if (task.data.workflow_id) setWorkflowSelection({conversationId:task.data.conversation_id,id:task.data.workflow_id}); }}>Open conversation{task.data.workflow_id ? ' and workflow' : ''}<Icon name="arrow" size={13}/></button></article>)}</div>}
    </aside> : null}
  </>;
}

function ActionSummary({ action }: { action: ActionPreview }) {
  const raw = action.data.preview;
  const preview = raw.request && typeof raw.request === 'object' && !Array.isArray(raw.request) ? raw.request as Record<string, unknown> : raw.data && typeof raw.data === 'object' && !Array.isArray(raw.data) ? {...raw,...raw.data as Record<string,unknown>} : raw;
  const fields = ['title', 'objective', 'description', 'task_kind', 'jurisdiction', 'operation_date', 'controller_mode','conops'];
  return <dl className="companion-action-summary">{fields.filter(key => typeof preview[key] === 'string').map(key => <div key={key}><dt>{({ task_kind: 'Task', jurisdiction: 'Country or framework', operation_date: 'Operation date', controller_mode: 'Execution method', conops:'Intended operation' } as Record<string, string>)[key] ?? key.charAt(0).toUpperCase() + key.slice(1)}</dt><dd>{key==='task_kind'||key==='controller_mode'?String(preview[key]).replaceAll('_',' '):String(preview[key])}</dd></div>)}</dl>;
}

function WorkflowProgress({ workflow, busy, control, open }: { workflow: DomainRecord; busy: boolean; control: (action: 'advance' | 'pause' | 'resume' | 'cancel') => Promise<void>; open: () => void }) {
  const execution = workflow.data.execution as { step_count?: number; last_error?: string } | undefined;
  return <article className="companion-workflow"><header><h3>{workflow.title}</h3><StateTag state={workflow.status}/></header><p>{execution?.step_count===undefined?'Step count not reported':`${execution.step_count} recorded steps`}</p>{execution?.last_error ? <Notice danger>{execution.last_error}</Notice> : null}<div className="companion-preview-buttons">{workflow.status === 'Queued' ? <p>Waiting for the workflow worker.</p> : null}{activeStates.includes(workflow.status) ? <button className="secondary" disabled={busy} onClick={() => void control('pause')}>Pause</button> : ['Paused', 'Blocked'].includes(workflow.status) ? <button className="secondary" disabled={busy} onClick={() => void control('resume')}>Resume</button> : null}{!['Cancelled', 'Needs Review', 'Failed'].includes(workflow.status) ? <button className="secondary" disabled={busy} onClick={() => void control('cancel')}>Cancel</button> : null}</div><button className="text-button" onClick={open}>Open workflow details<Icon name="arrow" size={13}/></button></article>;
}
