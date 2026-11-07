import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AgentWorkspace } from './AgentWorkspace';
import type { User } from './api';

vi.mock('./AgentCompanion', () => ({ AgentCompanion: () => null }));
const actor: User = { id: 'isolated-planner', email: 'planner@example.invalid', role: 'planner', organisation_id: 'isolated-org' };
const kinds = ['mission', 'aircraft', 'personnel', 'site', 'route', 'permission', 'case', 'alert', 'schedule'];
const roles = Object.fromEntries(['regulatory_research', 'authorisation_preparation', 'site_assessment', 'scheduling_proposal', 'maintenance_planning', 'cross_border_readiness', 'fleet_sharing_review'].map(kind => [kind, ['planner']]));
const record = { id: 'isolated-existing-mission', kind: 'mission', title: 'Existing mission evidence', status: 'Draft', version: 3, data: {} };
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(done => { resolve = done; }); return { promise, resolve }; }
function install(records: (kind: string, init: RequestInit) => Promise<Response>) {
  const fetch = vi.fn((path: string, init: RequestInit = {}) => {
    if (path === '/api/v1/agent-capabilities') return Promise.resolve(json({ task_roles: roles, tools: [] }));
    if (path.startsWith('/api/v1/records/')) return records(path.split('/').at(-1)!, init);
    return Promise.resolve(json({ items: [] }));
  });
  vi.stubGlobal('fetch', fetch); return fetch;
}
function view(user = actor, token = 'isolated-token', revision = 0) {
  return <AgentWorkspace token={token} user={user} revision={revision} changed={() => undefined} />;
}
async function prepare() {
  const button = await screen.findByRole('button', { name: /Regulatory research/ });
  await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(button);
  for (const [label, value] of [['What do you want to achieve?', 'Keep this unsent evidence review'], ['Jurisdiction', 'EU'], ['Operation date', '2026-11-07'], ['Execution method', 'native']]) {
    fireEvent.change(screen.getByLabelText(label), { target: { value } });
  }
}
afterEach(() => { cleanup(); sessionStorage.clear(); vi.unstubAllGlobals(); });

describe('workflow saved-context recovery', () => {
  it('blocks scope creation while context is pending and does not present pending data as empty', async () => {
    const pending = deferred<Response>();
    const fetch = install(kind => kind === 'mission' ? pending.promise : Promise.resolve(json({ items: [] })));
    render(view()); await prepare();
    expect(screen.getByText('Loading saved workflow records…')).toBeTruthy();
    expect(screen.queryByText(/Create an operation proposal or evidence record first/)).toBeNull();
    expect((screen.getByRole('button', { name: 'Create workflow' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.submit(screen.getByLabelText('What do you want to achieve?').closest('form')!);
    expect(fetch.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true);
    await act(async () => pending.resolve(json({ items: [record] })));
    await screen.findByRole('checkbox', { name: /Existing mission evidence/ });
    expect((screen.getByRole('button', { name: 'Create workflow' }) as HTMLButtonElement).disabled).toBe(false);
  });

  it('shows a failed context read and retries only record GETs while keeping the draft', async () => {
    let missions = 0;
    const fetch = install(kind => Promise.resolve(kind === 'mission' && ++missions === 1
      ? json({ detail: 'Isolated context outage' }, 503) : json({ items: kind === 'mission' ? [record] : [] })));
    render(view()); await prepare();
    await screen.findByRole('button', { name: 'Retry workflow records' });
    expect(screen.getByRole('alert').textContent).toContain('Saved workflow records are unavailable');
    expect(screen.queryByText(/Create an operation proposal or evidence record first/)).toBeNull();
    expect((screen.getByRole('button', { name: 'Create workflow' }) as HTMLButtonElement).disabled).toBe(true);
    const before = fetch.mock.calls.length;
    fireEvent.click(screen.getByRole('button', { name: 'Retry workflow records' }));
    await screen.findByRole('checkbox', { name: /Existing mission evidence/ });
    expect((screen.getByLabelText('What do you want to achieve?') as HTMLTextAreaElement).value).toBe('Keep this unsent evidence review');
    const retry = fetch.mock.calls.slice(before);
    expect(retry.map(([path]) => path).sort()).toEqual(kinds.map(kind => `/api/v1/records/${kind}`).sort());
    expect(fetch.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true);
  });

  it('uses the empty guidance only after a valid complete empty response', async () => {
    install(() => Promise.resolve(json({ items: [] })));
    render(view()); await prepare();
    await screen.findByText(/Create an operation proposal or evidence record first/);
    expect(screen.queryByRole('button', { name: 'Retry workflow records' })).toBeNull();
    expect((screen.getByRole('button', { name: 'Create workflow' }) as HTMLButtonElement).disabled).toBe(false);
  });

  it('fails closed for malformed collection records', async () => {
    install(kind => Promise.resolve(json({ items: kind === 'mission' ? [{ ...record, version: 0 }] : [] })));
    render(view()); await prepare();
    await screen.findByRole('button', { name: 'Retry workflow records' });
    expect(screen.getByRole('alert').textContent).toContain('response was not valid');
    expect((screen.getByRole('button', { name: 'Create workflow' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('does not let an obsolete revision response restore old records after current context loads', async () => {
    const old = deferred<Response>(); let missions = 0;
    install(kind => kind === 'mission' && ++missions === 1 ? old.promise : Promise.resolve(json({ items: kind === 'mission' ? [record] : [] })));
    const mounted = render(view()); await prepare();
    mounted.rerender(view(actor, 'isolated-token', 1));
    await screen.findByRole('checkbox', { name: /Existing mission evidence/ });
    await act(async () => old.resolve(json({ items: [{ ...record, id: 'isolated-obsolete', title: 'Obsolete private evidence' }] })));
    expect(screen.queryByText('Obsolete private evidence')).toBeNull();
    expect(screen.getByRole('checkbox', { name: /Existing mission evidence/ })).toBeTruthy();
  });

  it.each(['actor', 'tenant', 'token', 'role'])('retires an old planner and ignores late records after a %s change', async field => {
    const old = deferred<Response>(); let missions = 0;
    const fetch = install(kind => kind === 'mission' && ++missions === 1 ? old.promise : Promise.resolve(json({ items: [] })));
    const mounted = render(view()); await prepare();
    const nextActor = { ...actor, ...(field === 'actor' ? { id: 'isolated-other' } : field === 'tenant' ? { organisation_id: 'isolated-other-org' } : field === 'role' ? { role: 'reviewer' } : {}) };
    mounted.rerender(view(nextActor, field === 'token' ? 'isolated-new-token' : 'isolated-token'));
    expect(screen.queryByLabelText('What do you want to achieve?')).toBeNull();
    await act(async () => old.resolve(json({ items: [record] })));
    expect(screen.queryByText('Existing mission evidence')).toBeNull();
    expect(fetch.mock.calls.every(([, init]) => !init?.method || init.method === 'GET')).toBe(true);
  });
});
