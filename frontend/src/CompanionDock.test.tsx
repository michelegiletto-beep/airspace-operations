import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CompanionDock } from './CompanionDock';
import type { ActionPreview, CompanionConversation, CompanionDetail, CompanionMessage, CompanionTask, ModelStatus } from './companionApi';
import type { DomainRecord, User } from './api';

vi.mock('./companionRuntime', () => ({ loadCompanionRuntime: vi.fn().mockRejectedValue(new Error('Isolated renderer outage')) }));
const user: User = { id: 'test-actor', email: 'actor@example.invalid', organisation_id: 'test-tenant', role: 'regulatory' };
const model: ModelStatus = { state: 'Not Installed', mode: 'local_causal', version: null, message: 'The local model is not installed.', hosted_provider: false, generative_model_used: false };
const base = { version: 1, created_by: user.id, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' };
const conversation: CompanionConversation = { ...base, id: 'test-conversation', kind: 'companion_conversation', title: 'Isolated conversation', version: 5, status: 'Ready', data: { owner_actor_id: user.id, workspace: 'operations', context_record_versions: {}, active_message_id: null, next_turn: 1 } };
const userMessage: CompanionMessage = { ...base, id: 'test-message', kind: 'companion_message', title: 'Isolated request', status: 'Saved', data: { role: 'user', text: 'Remember to review the operator procedure.' } };
const action: ActionPreview = { ...base, id: 'test-action', kind: 'companion_action', title: 'Task preview', status: 'Awaiting Confirmation', version: 3, data: { owner_actor_id: user.id, expires_at:'2099-01-01T00:00:00Z', kind: 'task_draft', label: 'Save this request as a personal task', preview: { title: 'Review the procedure', description: 'Review the operator procedure.', effect: 'Creates a personal task only.' } } };
const task: CompanionTask = { ...base, id: 'test-task', kind: 'companion_task', title: 'Review the procedure', status: 'Open', version: 7, data: { owner_actor_id: user.id, conversation_id: conversation.id, source_message_id: userMessage.id, description: 'Review the operator procedure.', due_at: null, completed_at: null, created_from_action_id: action.id } };

function install(options: { restored?: boolean; action?: ActionPreview; conflict?: boolean; running?: boolean; text?: string; workflow?: boolean; taskConflict?: boolean; retry?: boolean; case?: boolean; linked?: boolean; procedure?: boolean } = {}) {
  let tasks: CompanionTask[] = options.restored ? [{...task,data:{...task.data,...(options.linked?{workflow_id:'test-workflow'}:{})}}] : [];
  let detail: CompanionDetail = { conversation, messages: [], action_previews: options.action ? [options.action] : [], tasks: [], active_job: null, model_status: model };
  if (options.text) detail.messages = [{ ...userMessage, id: 'test-reply', data: { role: 'assistant', text: options.text, reply_kind: 'fallback', missing_inputs: ['Select the relevant aircraft record.'] } }];
  if (options.retry) detail.messages = [{ ...userMessage, data: { ...userMessage.data, request: { jurisdiction: 'LU', operation_date: '2026-02-03' } } }, { ...userMessage, id: 'test-reply', data: { role: 'assistant', text: 'Saved fallback guidance.', reply_kind: 'fallback', reply_to_message_id: userMessage.id, next_steps: [{ id: 'step-1', text: 'Review the approved procedure.' }] } }];
  if (options.procedure) { detail.messages=[userMessage,{...userMessage,id:'test-procedure-guidance',data:{role:'assistant',text:'Use the approved operator procedure and accountable incident coordinator.',reply_kind:'procedure_guidance',reply_to_message_id:userMessage.id}}];detail.model_status={...model,state:'Procedure Required',message:'Approved operator procedures govern response.',generative_model_used:false}; }
  if (options.running) detail.active_job = { id: 'test-job', kind: 'companion_reply', state: 'Running', version: 1, payload: { conversation_id: conversation.id, message_id: userMessage.id } };
  const workflow: DomainRecord = { ...base, id: 'test-workflow', kind: 'agent_workflow', title: 'Isolated source workflow', status: 'Running', version: 9, data: { execution: { step_count: 2 }, trace: [] } };
  const fetcher = vi.fn(async (url: string, init: RequestInit = {}) => {
    const body = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
    if (url === '/api/v1/companion/catalog') return body({ workspaces: [], action_kinds: ['task_draft', 'case_draft', 'workflow_draft'], model_status: model });
    if (url === '/api/v1/companion/conversations' && init.method === 'POST') return body(conversation, 201);
    if (url === '/api/v1/companion/conversations') return body({ items: options.restored || options.action || options.running || options.text || options.retry || options.procedure ? [conversation] : [] });
    if (url === '/api/v1/companion/tasks') return body({ items: tasks });
    if (url === '/api/v1/companion/tasks/test-task' && init.method === 'PUT') {
      if (options.taskConflict) return body({ detail: 'Task changed. Reload its current version.' }, 409);
      tasks = [{ ...task, status: JSON.parse(init.body as string).state, version: 8 }]; return body(tasks[0]);
    }
    if (url.endsWith('/messages') && init.method === 'POST') {
      const job = { id: 'test-job', kind: 'companion_reply', state: 'Queued', version: 1, payload: { conversation_id: conversation.id, message_id: userMessage.id } };
      detail = { ...detail, conversation: { ...conversation, version: 6 }, messages: [userMessage], active_job: job };
      return body({ conversation: detail.conversation, user_message: userMessage, job, reply: null, action_previews: [], model_status: model }, 202);
    }
    if (url.endsWith('/cancel')) { detail = { ...detail, conversation: { ...conversation, version: 6 }, active_job: null }; return body({ conversation: detail.conversation }); }
    if (url.endsWith('/confirm')) {
      if (options.conflict) return body({ detail: 'The selected record changed. Review a new preview.' }, 409);
      const confirmed = { ...(options.action ?? action), status: 'Confirmed', version: 4 };
      tasks = [task]; detail = { ...detail, action_previews: [confirmed] };
      return body({ conversation, action: confirmed, task, ...(options.workflow ? { workflow } : {}), ...(options.case ? { case: { ...base, id: 'test-case', title: 'Isolated intended operation', kind: 'case', status: 'Draft', data: {} } } : {}) });
    }
    if (url.endsWith('/reject')) { detail = { ...detail, action_previews: [{ ...(options.action ?? action), status: 'Rejected', version: 4 }] }; return body({ conversation, action: detail.action_previews[0] }); }
    if (url === '/api/v1/companion/conversations/test-conversation') return body(detail);
    if (url === '/api/v1/agent-workflows/test-workflow') return body(workflow);
    if (url.endsWith('/control')) return body(workflow);
    if (url.startsWith('/api/v1/records/')) return body({ items: [] });
    return body({ detail: 'Unexpected test endpoint: ' + url }, 404);
  });
  vi.stubGlobal('fetch', fetcher);
  return fetcher;
}

function mount(extra: Partial<Parameters<typeof CompanionDock>[0]> = {}) {
  return render(<CompanionDock token="isolated-test-token" user={user} workspace="operations" workspaceLabel="Operations" revision={0} changed={() => undefined} open onOpenChange={() => undefined} openWorkflow={() => undefined} {...extra}/>);
}
async function selectConversation() { await screen.findByRole('option', { name: conversation.title }); fireEvent.change(screen.getByLabelText('Saved conversation'), { target: { value: conversation.id } }); }
beforeEach(() => { sessionStorage.clear(); localStorage.clear(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); sessionStorage.clear(); localStorage.clear(); });

describe('private contextual companion', () => {
  it('guides an empty workspace without starting a task or implying an installed model', async () => {
    const fetcher = install(); mount();
    await screen.findByText('The local model is not installed.');
    fireEvent.click(screen.getByRole('button', { name: 'Help me plan an intended operation.' }));
    expect((screen.getByLabelText('Your request') as HTMLTextAreaElement).value).toBe('Help me plan an intended operation.');
    expect(fetcher.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false);
    expect(screen.queryByText('Local model response')).toBeNull();
  });

  it('saves only the user request, preserves blank operational inputs and distinguishes a queued worker', async () => {
    const fetcher = install(); mount();
    fireEvent.change(screen.getByLabelText('Your request'), { target: { value: userMessage.data.text } });
    fireEvent.click(screen.getByRole('button', { name: 'Send' }));
    await screen.findByText('Request queued');
    const calls = fetcher.mock.calls.filter(([, init]) => init?.method === 'POST');
    expect(JSON.parse(calls[0][1]?.body as string)).toEqual({ workspace: 'operations', context_record_ids: [] });
    expect(JSON.parse(calls[1][1]?.body as string)).toEqual({ message: userMessage.data.text, expected_version: 5 });
    expect(screen.getAllByText('Waiting for the worker').length).toBeGreaterThan(0);
    expect(screen.queryByText('Local model response')).toBeNull();
    expect(fetcher.mock.calls.some(([url]) => url.endsWith('/confirm'))).toBe(false);
  });

  it('confirms an actual saved preview with both versions before a task is created', async () => {
    const fetcher = install({ action }); mount(); await selectConversation();
    await screen.findByText(action.data.label);
    expect(fetcher.mock.calls.some(([url]) => url.endsWith('/confirm'))).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: 'Confirm and save task' }));
    await screen.findByText('Confirmed');
    const call = fetcher.mock.calls.find(([url]) => url.endsWith('/confirm'))!;
    expect(JSON.parse(call[1]?.body as string)).toEqual({ expected_version: 5, expected_action_version: 3 });
    fireEvent.click(screen.getByRole('tab', { name: /Tasks/ }));
    expect(await screen.findByRole('heading', { name: task.title })).toBeTruthy();
  });

  it('keeps stale preview rejection visible and does not fabricate a completed action', async () => {
    install({ action, conflict: true }); mount(); await selectConversation();
    fireEvent.click(await screen.findByRole('button', { name: 'Confirm and save task' }));
    expect(await screen.findByText('The selected record changed. Review a new preview.')).toBeTruthy();
    expect(screen.queryByText('Confirmed')).toBeNull(); expect(screen.getByText('Awaiting Confirmation')).toBeTruthy();
  });

  it('rejects a preview separately without creating any task', async () => {
    const fetcher = install({ action }); mount(); await selectConversation();
    fireEvent.click(await screen.findByRole('button', { name: 'Dismiss' }));
    await screen.findByText('Rejected');
    const call = fetcher.mock.calls.find(([url]) => url.endsWith('/reject'))!;
    expect(JSON.parse(call[1]?.body as string)).toEqual({ expected_version: 5, expected_action_version: 3 });
    expect(fetcher.mock.calls.some(([url]) => url.endsWith('/confirm'))).toBe(false);
  });

  it('cancels a running reply through the versioned conversation endpoint', async () => {
    const fetcher = install({ running: true }); mount(); await selectConversation();
    fireEvent.click(await screen.findByRole('button', { name: 'Cancel request' }));
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Cancel request' })).toBeNull());
    const call = fetcher.mock.calls.find(([url]) => url.endsWith('/cancel'))!;
    expect(JSON.parse(call[1]?.body as string)).toEqual({ expected_version: 5 });
  });

  it('closing the assistant does not silently cancel a running request', async () => {
    const fetcher = install({ running: true }); const close = vi.fn(); mount({ onOpenChange: close }); await selectConversation();
    await screen.findByRole('button', { name: 'Cancel request' });
    fireEvent.click(screen.getByRole('button', { name: 'Close assistant panel' }));
    expect(close).toHaveBeenCalledWith(false);
    expect(fetcher.mock.calls.some(([url]) => url.endsWith('/cancel'))).toBe(false);
  });

  it('restores persisted tasks and sends a versioned state change', async () => {
    const fetcher = install({ restored: true }); mount();
    fireEvent.click(await screen.findByRole('tab', { name: /Tasks/ }));
    fireEvent.change(await screen.findByLabelText(`Task state for ${task.title}`), { target: { value: 'Completed' } });
    await waitFor(() => expect((screen.getByLabelText(`Task state for ${task.title}`) as HTMLSelectElement).value).toBe('Completed'));
    const call = fetcher.mock.calls.find(([, init]) => init?.method === 'PUT')!;
    expect(JSON.parse(call[1]?.body as string)).toEqual({ expected_version: 7, state: 'Completed' });
  });

  it('keeps the saved task state after a failed version check', async () => {
    install({ restored: true, taskConflict: true }); mount(); fireEvent.click(await screen.findByRole('tab', { name: /Tasks/ }));
    fireEvent.change(await screen.findByLabelText(`Task state for ${task.title}`), { target: { value: 'Completed' } });
    await screen.findByText('Task changed. Reload its current version.');
    expect((screen.getByLabelText(`Task state for ${task.title}`) as HTMLSelectElement).value).toBe('Open');
  });

  it('identifies fallback guidance and renders hostile content as text', async () => {
    install({ text: '<img src=x onerror="window.stolen=true">' }); const view = mount(); await selectConversation();
    await screen.findByText('<img src=x onerror="window.stolen=true">');
    expect(screen.getByText('Basic guidance without a model response')).toBeTruthy();
    expect(screen.getByText('Select the relevant aircraft record.')).toBeTruthy();
    expect(view.container.querySelector('img')).toBeNull();
  });

  it('explains that confirmation starts internal workflow work and shows its real progress', async () => {
    const workflowAction: ActionPreview = { ...action, data: { ...action.data, kind: 'workflow_draft', label: 'Prepare source research', preview: { request: { task_kind: 'regulatory_research', jurisdiction: 'EU', operation_date: '2026-01-01', controller_mode: 'local_causal' }, effect: 'Starts internal source work and requires independent review.' } } };
    const fetcher = install({ action: workflowAction, workflow: true }); mount(); await selectConversation();
    expect(await screen.findByText(/Confirmation starts this internal workflow/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Confirm and start workflow' }));
    await screen.findByText('2 recorded steps');
    fireEvent.click(screen.getByRole('button', { name: 'Pause' }));
    await waitFor(() => expect(fetcher.mock.calls.some(([url]) => url.endsWith('/control'))).toBe(true));
    const call = fetcher.mock.calls.find(([url]) => url.endsWith('/control'))!;
    expect(JSON.parse(call[1]?.body as string)).toEqual({ expected_version: 9, action: 'pause' });
  });

  it('renders the backend structured next steps and retries only with the original explicit inputs', async () => {
    const fetcher = install({ retry: true }); mount(); await selectConversation();
    await screen.findByText('Review the approved procedure.');
    fireEvent.click(screen.getByRole('button', { name: 'Retry this request' }));
    await screen.findByText('Request queued');
    const call = fetcher.mock.calls.find(([url, init]) => url.endsWith('/messages') && init?.method === 'POST')!;
    expect(JSON.parse(call[1]?.body as string)).toEqual({ message: userMessage.data.text, expected_version: 5, jurisdiction: 'LU', operation_date: '2026-02-03' });
  });

  it('does not enable an unsupported action kind', async () => {
    const unsupported = { ...action, data: { ...action.data, kind: 'aircraft_command' } } as unknown as ActionPreview;
    const fetcher = install({ action: unsupported }); mount(); await selectConversation();
    const confirm = await screen.findByRole('button', { name: 'Unsupported action' }) as HTMLButtonElement;
    expect(confirm.disabled).toBe(true); fireEvent.click(confirm);
    expect(fetcher.mock.calls.some(([url]) => url.endsWith('/confirm'))).toBe(false);
  });

  it('does not enable confirmation for an action owned by another actor', async () => {
    const other = { ...action, data: { ...action.data, owner_actor_id: 'different-test-actor' } };
    const fetcher = install({ action: other }); mount(); await selectConversation();
    const confirm = await screen.findByRole('button', { name: 'Confirm and save task' }) as HTMLButtonElement;
    expect(confirm.disabled).toBe(true); fireEvent.click(confirm);
    expect(fetcher.mock.calls.some(([url]) => url.endsWith('/confirm'))).toBe(false);
  });

  it('provides a concrete next step after the server creates a draft case', async () => {
    const caseAction: ActionPreview = { ...action, data: { ...action.data, kind: 'case_draft', label: 'Create a draft authorisation case', preview: { title: 'Isolated intended operation', data: { jurisdiction: 'LU' } } } };
    install({ action: caseAction, case: true }); const navigate = vi.fn(); mount({ openWorkspace: navigate }); await selectConversation();
    fireEvent.click(await screen.findByRole('button', { name: 'Confirm and create case' }));
    await screen.findByRole('heading', { name: 'Draft case saved' });
    fireEvent.click(screen.getByRole('button', { name: 'Open authorisation cases' }));
    expect(navigate).toHaveBeenCalledWith('authorisations');
    expect(screen.queryByText('Approved')).toBeNull();
  });

  it('disables an expired preview and explains how to obtain a current one', async () => {
    const expired = { ...action, data: { ...action.data, expires_at: '2020-01-01T00:00:00Z' } };
    const fetcher=install({ action: expired }); mount(); await selectConversation();
    await screen.findByText('Expired');
    expect(screen.getByText('This proposal expired. Send a new request for a current preview.')).toBeTruthy();
    const confirm=screen.getByRole('button',{name:'Confirm and save task'}) as HTMLButtonElement;
    expect(confirm.disabled).toBe(true);fireEvent.click(confirm);
    expect(fetcher.mock.calls.some(([url])=>url.endsWith('/confirm'))).toBe(false);
  });

  it('distinguishes a tracking task state change from workflow cancellation', async () => {
    const fetcher=install({restored:true,linked:true});mount();
    fireEvent.click(await screen.findByRole('tab',{name:/Tasks/}));
    expect(await screen.findByText('This changes your tracking task only. Use the workflow controls to pause or cancel the workflow.')).toBeTruthy();
    fireEvent.change(screen.getByLabelText(`Tracking task state for ${task.title}`),{target:{value:'Cancelled'}});
    await waitFor(()=>expect(fetcher.mock.calls.some(([,init])=>init?.method==='PUT')).toBe(true));
    expect(fetcher.mock.calls.some(([url])=>url.endsWith('/control'))).toBe(false);
  });

  it('identifies deterministic procedure guidance without implying model outage or offering an AI retry', async () => {
    install({procedure:true});const navigate=vi.fn();mount({openWorkspace:navigate});await selectConversation();
    await screen.findByText('Use the approved operator procedure and accountable incident coordinator.');
    expect(screen.getAllByText('Approved procedure required').length).toBeGreaterThan(0);
    expect(screen.queryByText('Basic guidance without a model response')).toBeNull();
    expect(screen.queryByText('Local model response')).toBeNull();
    expect(screen.queryByRole('button',{name:'Retry this request'})).toBeNull();
    fireEvent.click(screen.getByRole('button',{name:'Open incidents'}));
    expect(navigate).toHaveBeenCalledWith('incidents');
  });

  it('keeps conversation-changing controls disabled while confirmation is pending and ignores a late older detail', async()=>{
    const caseAction:ActionPreview={...action,data:{...action.data,kind:'case_draft',label:'Prepare an isolated draft case'}};
    const fetcher=install({action:caseAction});const original=fetcher.getMockImplementation()!;
    let resolve!:(response:Response)=>void;
    fetcher.mockImplementation(async(url,init)=>url.endsWith('/confirm')?new Promise<Response>(done=>{resolve=done;}):original(url,init));
    mount();await selectConversation();
    fireEvent.click(await screen.findByRole('button',{name:'Confirm and create case'}));
    expect((screen.getByLabelText('Saved conversation') as HTMLSelectElement).disabled).toBe(true);
    expect((screen.getByRole('tab',{name:/Tasks/}) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole('button',{name:'New'}) as HTMLButtonElement).disabled).toBe(true);
    resolve(new Response(JSON.stringify({conversation:{...conversation,version:6},action:{...caseAction,status:'Confirmed',version:4},case:{...base,id:'test-case',kind:'case',status:'Draft',title:'Delayed isolated draft',data:{}}})));
    await screen.findByRole('heading',{name:'Draft case saved'});
    await waitFor(()=>expect(screen.getByText('Confirmed')).toBeTruthy());
    fireEvent.change(screen.getByLabelText('Saved conversation'),{target:{value:''}});
    expect(screen.queryByRole('heading',{name:'Draft case saved'})).toBeNull();
  });
});
