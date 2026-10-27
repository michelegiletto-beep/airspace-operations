import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import Records from './Records';
import type { DomainRecord, User } from './api';

const user: User = { id: 'test-reviewer', email: 'reviewer@example.invalid', role: 'reviewer', organisation_id: 'isolated-test-org' };
const testRecord: DomainRecord = { id: 'test-record', kind: 'case', title: 'Isolated case fixture', status: 'Under Review', data: {}, version: 2, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', created_by: 'test-reviewer' };
afterEach(() => { cleanup(); vi.unstubAllGlobals(); sessionStorage.clear(); });
describe('real record workflow interface', () => {
  it('shows an honest empty workspace without operational activity', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ items: [], total: 0 }))));
    render(<Records kindId="mission" token="isolated-test-token" user={user} revision={0} changed={() => undefined} />);
    await screen.findByText('No missions recorded');
    expect(screen.getByText(/No flights have been recorded/)).toBeTruthy();
  });
  it('blocks self approval before sending a transition request', async () => {
    const fetch = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ items: [testRecord] })))); vi.stubGlobal('fetch', fetch);
    render(<Records kindId="case" token="isolated-test-token" user={user} revision={0} changed={() => undefined} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Isolated case fixture' }));
    fireEvent.change(screen.getByLabelText('Requested state'), { target: { value: 'Approved' } });
    expect(screen.getByText(/You created this record/)).toBeTruthy();
    expect((screen.getByRole('button', { name: 'Record transition' }) as HTMLButtonElement).disabled).toBe(true);
    expect(fetch.mock.calls.every((call: unknown[]) => !(call[1] as RequestInit)?.method)).toBe(true);
  });
  it('uses expected_version and preserves server conflict evidence', async () => {
    const record = { ...testRecord, data: { jurisdiction: 'LU', legal_route: 'SORA', owner: 'Operator', aircraft_configuration_id: 'isolated-config', conops: 'User-entered proposed operation for software testing.', _prepared_by: 'test-reviewer', _approvals: [] } };
    const fetch = vi.fn().mockImplementation((_url: string, init: RequestInit) => Promise.resolve(init?.method === 'PUT' ? new Response(JSON.stringify({ detail: 'Revision conflict' }), { status: 409 }) : new Response(JSON.stringify({ items: [record] })))); vi.stubGlobal('fetch', fetch);
    render(<Records kindId="case" token="isolated-test-token" user={user} revision={0} changed={() => undefined} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Isolated case fixture' }));
    fireEvent.click(screen.getByRole('button', { name: 'Save revision' }));
    await screen.findByText('Revision conflict');
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(3));
    const call = fetch.mock.calls.find((args: unknown[]) => (args[1] as RequestInit)?.method === 'PUT')!;
    const sent = JSON.parse((call[1] as RequestInit).body as string) as Record<string, unknown>;
    expect(sent.expected_version).toBe(2);
    expect(sent.data).not.toHaveProperty('_prepared_by');
    expect(sent.data).not.toHaveProperty('_approvals');
    expect(screen.getByRole('button', { name: 'Save revision' })).toBeTruthy();
  });
  it('blocks a state decision while the displayed record has unsaved edits', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({ items: [testRecord] })))));
    render(<Records kindId="case" token="isolated-test-token" user={user} revision={0} changed={() => undefined} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Isolated case fixture' }));
    fireEvent.change(screen.getByLabelText('Title'), { target: { value: 'An unsaved changed ConOps title' } });
    expect((screen.getByRole('button', { name: 'Record transition' }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(/decision must refer to the saved record revision/)).toBeTruthy();
  });
});
