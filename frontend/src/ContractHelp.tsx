import { useState } from 'react';
import { errorMessage, request, saveBlob } from './api';
import { JsonView, Notice } from './components';

export function ContractHelp({ token, name }: { token: string; name: string }) {
  const [schema, setSchema] = useState<unknown>(null); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  async function load() {
    if (schema || busy) return; setBusy(true); setError('');
    try { const response = await request<{ contracts: Record<string, unknown> }>('/contracts', token); if (!response.contracts[name]) throw new Error(`${name} is not available in the server contract register.`); setSchema(response.contracts[name]); }
    catch (cause) { setError(errorMessage(cause)); } finally { setBusy(false); }
  }
  return <details className="contract-help" onToggle={event => { if (event.currentTarget.open) void load(); }}><summary>Inspect {name} input schema</summary>{busy ? <p className="small muted">Loading authenticated server contract…</p> : null}{error ? <Notice danger>{error}</Notice> : null}{schema ? <><p className="small muted">This JSON schema comes from the running backend. The server replaces actor_id with the authenticated user. A valid schema does not establish the factual correctness or operational acceptance of supplied inputs.</p><JsonView value={schema} /><button type="button" className="secondary" onClick={() => saveBlob(new Blob([JSON.stringify(schema, null, 2)], { type: 'application/schema+json' }), `${name}.schema.json`)}>Download {name} schema</button></> : null}</details>;
}
