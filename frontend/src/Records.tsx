import { useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { displayDate, downloadPackage, errorMessage, parseObject, request, writableData } from './api';
import type { Collection, DomainRecord, User } from './api';
import { Empty, JsonView, Notice, Panel, StateTag, Updated, useRemote } from './components';
import { canWriteRecord, formData, kinds, states, transitions } from './schema';
import { AlertAcknowledgement, EvidenceAttachment, IncidentWorkspace } from './RecordActions';
import type { Field, Kind } from './schema';
function inputValue(value: unknown, field: Field): string { return value === undefined ? '' : typeof value === 'object' && (!Array.isArray(value) || field.type === 'json') ? JSON.stringify(value, null, 2) : Array.isArray(value) ? value.join(', ') : String(value); }

interface Props { kindId: string; token: string; user: User; revision: number; changed: () => void; createIntent?:number }
export default function Records({ kindId, token, user, revision, changed, createIntent=0 }: Props) {
  const kind = kinds[kindId];
  const result = useRemote<Collection<DomainRecord>>(`/records/${kindId}`, token, revision);
  const [search, setSearch] = useState(''); const [status, setStatus] = useState('');
  const [selected, setSelected] = useState<DomainRecord | 'new' | null>(null);
  const [notice, setNotice] = useState('');
  useEffect(()=>{if(createIntent>0)setSelected('new');},[createIntent]);
  const items = result.data?.items ?? [];
  const filterStates = Array.from(new Set([...states, ...items.map(item => item.status)]));
  const filtered = useMemo(() => items.filter(item => (!status || item.status === status) && (!search || `${item.title} ${item.id} ${JSON.stringify(item.data)}`.toLowerCase().includes(search.toLowerCase()))), [items, search, status]);
  const canWrite = canWriteRecord(kindId, user.role);
  return <><div className="section-toolbar"><div><h2>{kind.label}</h2><p className="muted small">{items.length} recorded · <Updated time={result.checkedAt} /></p></div>{canWrite ? <button className="primary" onClick={() => { setNotice(''); setSelected('new'); }}>+ New {kind.singular}</button> : <StateTag state="Read only" />}</div>
    {notice ? <Notice>{notice}</Notice> : null}
    {result.error ? <Notice danger>{result.error}</Notice> : null}
    <div className="filter-row"><label className="search-label"><span className="sr-only">Search {kind.label.toLowerCase()}</span><input type="search" placeholder={`Search ${kind.label.toLowerCase()}…`} value={search} onChange={event => setSearch(event.target.value)} /></label><label className="status-filter"><span className="sr-only">Filter by state</span><select value={status} onChange={event => setStatus(event.target.value)}><option value="">All states</option>{filterStates.map(state => <option key={state}>{state}</option>)}</select></label><button className="secondary" onClick={changed}>Refresh</button></div>
    {result.loading ? <p className="loading" role="status">Loading organisation records…</p> : items.length === 0 ? <Empty title={`No ${kind.label.toLowerCase()} recorded`}>{kind.empty}</Empty> : filtered.length === 0 ? <Empty title="No matching records">Clear the search or state filter to show recorded items.</Empty> : <div className="table-scroll"><table><thead><tr><th>Record</th><th>State</th><th>Jurisdiction / scope</th><th>Updated (UTC)</th><th>Revision</th></tr></thead><tbody>{filtered.map(item => <tr key={item.id} className={selected !== 'new' && selected?.id === item.id ? 'selected' : ''}><td><button className="record-link" onClick={() => { setNotice(''); setSelected(item); }}>{item.title}</button><span className="record-id">{item.id}</span></td><td><StateTag state={item.status} /></td><td>{String(item.data.jurisdiction ?? item.data.permission_type ?? item.data.evidence_type ?? 'Not recorded')}</td><td className="nowrap">{displayDate(item.updated_at)}</td><td><span className="revision">v{item.version}</span></td></tr>)}</tbody></table></div>}
    {selected ? <RecordEditor key={selected === 'new' ? `new-${kindId}` : `${selected.id}-${selected.version}`} kind={kind} record={selected === 'new' ? undefined : selected} token={token} user={user} close={() => setSelected(null)} onSaved={(message) => { setSelected(null); setNotice(message); changed(); }} /> : null}
  </>;
}
interface EditorProps { kind: Kind; record?: DomainRecord; token: string; user: User; close: () => void; onSaved: (message: string) => void }
export function RecordEditor({ kind, record, token, user, close, onSaved }: EditorProps) {
  const draftKey = `sl-airspace-draft:${user.organisation_id}:${user.id}:${kind.id}:${record?.id ?? 'new'}:${record?.version ?? 'new'}`;
  const savedDraft = (() => { try { const saved = sessionStorage.getItem(draftKey); return saved ? JSON.parse(saved) as { title: string; values: Record<string, string>; extra: string } : null; } catch { return null; } })();
  const [title, setTitle] = useState(savedDraft?.title ?? record?.title ?? '');
  const [values, setValues] = useState<Record<string, string>>(() => savedDraft?.values ?? Object.fromEntries(kind.fields.map(field => [field.key, inputValue(record?.data[field.key], field)])));
  const fieldKeys = new Set(kind.fields.map(field => field.key));
  const initialExtra = JSON.stringify(Object.fromEntries(Object.entries(writableData(record?.data ?? {})).filter(([key]) => !fieldKeys.has(key) && key !== 'reviewer_ids' && key !== 'attachment')), null, 2);
  const [extra, setExtra] = useState(savedDraft?.extra ?? initialExtra);
  const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  const availableStates = (transitions[record?.status ?? 'Draft'] ?? []).filter(value => !(kind.id === 'mission' && value === 'Approved'));
  const [state, setState] = useState(availableStates[0] ?? ''); const [reason, setReason] = useState(''); const [evidenceIds, setEvidenceIds] = useState('');
  const [reviewerIds, setReviewerIds] = useState<string[]>((record?.data.reviewer_ids as string[] | undefined) ?? []);
  const users = useRemote<Collection<{ id: string; email: string; role: string }>>('/users', token);
  const canWrite = canWriteRecord(kind.id, user.role) && !['Submitted', 'Superseded', 'Expired'].includes(record?.status ?? '');
  const canTransition = canWriteRecord(kind.id, user.role);
  const selfApproval = state === 'Approved' && record?.created_by === user.id;
  const reviewerMissing = state === 'Approved' && user.role !== 'reviewer';
  const hasChanges = Boolean(record && (title !== record.title || extra !== initialExtra || kind.fields.some(field => (values[field.key] ?? '') !== inputValue(record.data[field.key], field)) || JSON.stringify(reviewerIds) !== JSON.stringify(record.data.reviewer_ids ?? [])));
  function preserve(next: Partial<{ title: string; values: Record<string, string>; extra: string }>) {
    sessionStorage.setItem(draftKey, JSON.stringify({ title, values, extra, ...next }));
  }
  async function save(event: FormEvent) {
    event.preventDefault(); setError(''); setBusy(true);
    try {
      const data = { ...writableData(formData(kind, values, parseObject(extra))), reviewer_ids: reviewerIds, ...(kind.id === 'evidence' && record?.data.attachment ? { attachment: record.data.attachment, checksum: record.data.checksum } : {}) };
      await request(`/records/${kind.id}${record ? `/${record.id}` : ''}`, token, { method: record ? 'PUT' : 'POST', body: JSON.stringify({ title, data, ...(record ? { expected_version: record.version } : {}) }) });
      sessionStorage.removeItem(draftKey); onSaved(`${kind.label} updated. The server recorded this change and its accountable actor.`);
    } catch (cause) { setError(errorMessage(cause)); } finally { setBusy(false); }
  }
  async function transition(event: FormEvent) {
    event.preventDefault(); if (!record) return; setError(''); setBusy(true);
    try { await request(`/records/${kind.id}/${record.id}/transition`, token, { method: 'POST', body: JSON.stringify({ state, reason, expected_version: record.version, evidence_ids: evidenceIds.split(',').map(value => value.trim()).filter(Boolean) }) }); sessionStorage.removeItem(draftKey); onSaved(`State changed to ${state}. The decision and rationale are recorded.`); }
    catch (cause) { setError(errorMessage(cause)); } finally { setBusy(false); }
  }
  async function exportCase(format: 'json' | 'html') { if (!record) return; setBusy(true); setError(''); try { await downloadPackage(record.id, token, format); } catch (cause) { setError(errorMessage(cause)); } finally { setBusy(false); } }
  return <Panel title={record ? record.title : `New ${kind.singular}`} close={close}>
    {record ? <div className="record-meta"><StateTag state={record.status} /><span>Revision {record.version}</span><span>{record.id}</span></div> : <Notice>Record an intended operation or genuine evidence. Creating a draft does not record a flight or grant permission.</Notice>}
    {savedDraft ? <p className="small muted">Unsaved draft restored for this browser session.</p> : null}
    {error ? <Notice danger>{error}</Notice> : null}
    {record && kind.id === 'incident' ? <IncidentWorkspace record={record} token={token} /> : null}
    {record && kind.id === 'alert' ? <AlertAcknowledgement record={record} token={token} user={user} onSaved={onSaved} /> : null}
    {record && !canWrite && canTransition ? <Notice>This controlled state cannot be edited in place. Record an available transition or create a new draft revision.</Notice> : null}
    {kind.id !== 'alert' ? <form onSubmit={save} className="record-form"><label>Title<input required maxLength={240} value={title} disabled={!canWrite} onChange={event => { setTitle(event.target.value); preserve({ title: event.target.value }); }} /></label>
      <div className="field-grid">{kind.fields.map(field => <label key={field.key} className={field.type === 'textarea' || field.type === 'json' ? 'wide' : ''}>{field.label}{field.required ? ' *' : ''}{field.type === 'textarea' || field.type === 'json' ? <textarea rows={field.key === 'geometry' ? 6 : 3} required={field.required} disabled={!canWrite} value={values[field.key] ?? ''} onChange={event => { const next = { ...values, [field.key]: event.target.value }; setValues(next); preserve({ values: next }); }} /> : field.type === 'select' ? <select required={field.required} disabled={!canWrite} value={values[field.key] ?? ''} onChange={event => { const next = { ...values, [field.key]: event.target.value }; setValues(next); preserve({ values: next }); }}><option value="">Not recorded</option>{field.options?.map(option => <option key={option}>{option}</option>)}</select> : <input type={field.type === 'number' ? 'number' : field.type === 'date' ? 'date' : 'text'} step="any" required={field.required} disabled={!canWrite || (field.key === 'checksum' && Boolean(record?.data.attachment))} value={values[field.key] ?? ''} onChange={event => { const next = { ...values, [field.key]: event.target.value }; setValues(next); preserve({ values: next }); }} />}{field.help ? <span className="field-help">{field.help}</span> : null}</label>)}</div>
      <fieldset className="reviewer-field"><legend>Assigned independent reviewers</legend>{users.data?.items.filter(item => item.role === 'reviewer').length ? users.data.items.filter(item => item.role === 'reviewer').map(item => <label className="checkbox-row" key={item.id}><input type="checkbox" disabled={!canWrite || item.id === record?.created_by} checked={reviewerIds.includes(item.id)} onChange={event => setReviewerIds(previous => event.target.checked ? [...previous, item.id] : previous.filter(id => id !== item.id))} /><span>{item.email}<small>{item.id === record?.created_by ? 'Record creator — cannot approve this record' : item.id}</small></span></label>) : <p className="small muted">No active reviewer accounts returned. Your administrator must provision accountable reviewers.</p>}</fieldset>
      <details className="advanced"><summary>Additional structured fields</summary><p className="small muted">JSON object for additional domain fields. Named form fields take precedence. All changes are validated by the server.</p>{kind.id==='aircraft'?<p className="small muted">Imported utilisation and maintenance_completions must retain evidence_ref and the exact evidence_version of each source. Unknown revisions stay missing and block reservation/dispatch. Controlled work-order completion captures the actual evidence revision on the server.</p>:null}<label><span className="sr-only">Additional data JSON</span><textarea className="code-input" rows={5} value={extra} disabled={!canWrite} onChange={event => { setExtra(event.target.value); preserve({ extra: event.target.value }); }} /></label></details>
      {canWrite ? <div className="form-actions"><span className="small muted">* Required · Unsaved work retained for this session</span><button className="primary" disabled={busy}>{busy ? 'Saving…' : record ? 'Save revision' : 'Create draft'}</button></div> : null}
    </form> : null}
    {record && kind.id === 'evidence' ? <EvidenceAttachment record={record} token={token} user={user} unsaved={hasChanges} onSaved={onSaved} /> : null}
    {record ? <><section className="decision-section"><h3>Accountable state transition</h3><p className="small muted">Internal review and authority permission are separate decisions. The server enforces role, evidence, workflow and revision checks.</p>{canTransition && availableStates.length ? <form onSubmit={transition}><div className="field-grid"><label>Requested state<select value={state} onChange={event => setState(event.target.value)}>{availableStates.map(value => <option key={value}>{value}</option>)}</select></label><label>Supporting evidence IDs<input value={evidenceIds} onChange={event => setEvidenceIds(event.target.value)} placeholder="Comma-separated IDs" /></label><label className="wide">Decision rationale<textarea required minLength={3} rows={3} value={reason} onChange={event => setReason(event.target.value)} /></label></div>{selfApproval ? <Notice danger>You created this record. An independent authorised reviewer must decide approval.</Notice> : reviewerMissing ? <Notice>Approval requires the reviewer role. Administrator access alone does not grant reviewer authority.</Notice> : null}<button className="secondary" disabled={busy || hasChanges || selfApproval || reviewerMissing || (state === 'Approved' && !reviewerIds.includes(user.id))}>Record transition</button>{hasChanges ? <Notice>Save the edited draft before recording a state transition. The decision must refer to the saved record revision.</Notice> : null}{state === 'Approved' && !reviewerIds.includes(user.id) ? <p className="small muted">Your reviewer account must be assigned to this record.</p> : null}</form> : <p className="small muted">{availableStates.length ? 'Your role has read access.' : 'This state has no further workflow transitions.'}</p>}</section><details className="advanced"><summary>Record provenance</summary><dl className="definition-list"><dt>Created by</dt><dd>{record.created_by}</dd><dt>Created</dt><dd>{displayDate(record.created_at)}</dd><dt>Last updated</dt><dd>{displayDate(record.updated_at)}</dd><dt>Record revision</dt><dd>{record.version}</dd></dl><JsonView value={record.data} /></details>{kind.id === 'case' ? <div className="export-actions"><button className="secondary" onClick={() => exportCase('json')} disabled={busy || hasChanges}>Download controlled case JSON</button><button className="secondary" onClick={() => exportCase('html')} disabled={busy || hasChanges}>Download controlled case report (HTML)</button>{hasChanges ? <p className="small muted">Save the current draft before exporting its controlled revision.</p> : null}</div> : null}</> : null}
  </Panel>;
}




