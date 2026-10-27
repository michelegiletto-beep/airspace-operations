import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AlertAcknowledgement, EvidenceAttachment, IncidentWorkspace } from './RecordActions';
import type { DomainRecord, User } from './api';

const user: User = { id: 'isolated-actor', email: 'test@example.invalid', role: 'regulatory', organisation_id: 'isolated-test-org' };
const record: DomainRecord = { id: 'isolated-record', kind: 'evidence', title: 'Isolated software fixture', status: 'Draft', data: {}, version: 4, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', created_by: 'isolated-actor' };
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
describe('evidence content controls', () => {
  it('uploads the selected bytes, declared type and saved record version', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...record, version: 5 }))); vi.stubGlobal('fetch', fetch); const saved = vi.fn();
    render(<EvidenceAttachment record={record} token="isolated-token" user={user} unsaved={false} onSaved={saved} />);
    fireEvent.change(screen.getByLabelText('Evidence file (maximum 1 MB)'), { target: { files: [new File(['source evidence from isolated test'], 'isolated.txt', { type: 'text/plain' })] } });
    fireEvent.click(screen.getByRole('button', { name: 'Upload evidence content' }));
    await waitFor(() => expect(saved).toHaveBeenCalledTimes(1));
    const [path, init] = fetch.mock.calls[0] as [string, RequestInit]; expect(path).toBe('/api/v1/evidence/isolated-record/content'); expect(init.method).toBe('PUT');
    expect(JSON.parse(init.body as string)).toEqual({ original_name: 'isolated.txt', media_type: 'text/plain', content_base64: btoa('source evidence from isolated test'), expected_version: 4 });
  });
  it('blocks an upload that would silently discard unsaved edits', () => {
    render(<EvidenceAttachment record={record} token="isolated-token" user={user} unsaved onSaved={() => undefined} />);
    expect((screen.getByLabelText('Evidence file (maximum 1 MB)') as HTMLInputElement).disabled).toBe(true);
    expect((screen.getByRole('button', { name: 'Upload evidence content' }) as HTMLButtonElement).disabled).toBe(true);
  });
  it('does not offer upload authority to an independent reviewer', () => {
    render(<EvidenceAttachment record={record} token="isolated-token" user={{ ...user, role: 'reviewer' }} unsaved={false} onSaved={() => undefined} />);
    expect(screen.queryByRole('button', { name: 'Upload evidence content' })).toBeNull();
  });
});
describe('alert and incident actions', () => {
  it('records acknowledgement independently from notification delivery and action completion', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: 'Acknowledged' }))); vi.stubGlobal('fetch', fetch); const saved = vi.fn();
    render(<AlertAcknowledgement record={{ ...record, kind: 'alert', status: 'Unacknowledged', data: { mode: 'Historical Replay', notification: { sent: false, delivered: false, acknowledged: false, action_completed: false } } }} token="isolated-token" user={{ ...user, role: 'pilot' }} onSaved={saved} />);
    fireEvent.change(screen.getByLabelText('Acknowledgement reason'), { target: { value: 'Isolated software acknowledgement test' } });
    fireEvent.click(screen.getByRole('button', { name: 'Acknowledge alert and take ownership' }));
    await waitFor(() => expect(saved).toHaveBeenCalledTimes(1));
    const [path, init] = fetch.mock.calls[0] as [string, RequestInit]; expect(path).toBe('/api/v1/alerts/isolated-record/acknowledge'); expect(JSON.parse(init.body as string)).toEqual({ expected_version: 4, reason: 'Isolated software acknowledgement test' });
    expect(screen.getByText('Historical Replay')).toBeTruthy(); expect(screen.getAllByText('Not recorded')).toHaveLength(5);
  });
  it('retains a server concurrency rejection without reporting acknowledgement success', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Alert changed or already acknowledged' }), { status: 409 }))); const saved = vi.fn();
    render(<AlertAcknowledgement record={{ ...record, kind: 'alert', status: 'Unacknowledged' }} token="isolated-token" user={{ ...user, role: 'incident_coordinator' }} onSaved={saved} />);
    fireEvent.change(screen.getByLabelText('Acknowledgement reason'), { target: { value: 'Isolated concurrency test' } }); fireEvent.click(screen.getByRole('button', { name: 'Acknowledge alert and take ownership' }));
    await screen.findByText('Alert changed or already acknowledged'); expect(saved).not.toHaveBeenCalled();
  });
  it('shows missing approved procedures and an empty linked timeline without inventing instructions', async () => {
    const snapshot = { incident: { ...record, kind: 'incident' }, assessment: { status: 'Requires Accountable Action', owner: null, escalation: 'Missing Approved Escalation Policy', findings: ['No current approved procedure'], checklist: [] }, timeline: [], cache_generated_at: new Date().toISOString(), external_notification_status: 'Not Sent', degraded_export_notice: 'Export retains this snapshot only' };
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify(snapshot))); vi.stubGlobal('fetch', fetch);
    render(<IncidentWorkspace record={{ ...record, kind: 'incident' }} token="isolated-token" />);
    await screen.findByText('No current approved procedure'); expect(fetch.mock.calls[0][0]).toBe('/api/v1/incidents/isolated-record/workspace');
    expect(screen.getByText('No linked event records')).toBeTruthy(); expect(screen.getByText(/flight-critical instructions are not generated/)).toBeTruthy(); expect(screen.getByText('Not Sent')).toBeTruthy(); expect(screen.getByText(/seconds at last local check/)).toBeTruthy();
  });
});
