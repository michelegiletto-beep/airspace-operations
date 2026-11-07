import { useCallback, useEffect, useState } from 'react';
import { errorMessage, request } from './api';
import type { DomainRecord } from './api';

const contextKinds = ['mission', 'aircraft', 'personnel', 'site', 'route', 'permission', 'case', 'alert', 'schedule'];
type Snapshot = {
  token: string; revision: number; contextKey: string; attempt: number;
  records: DomainRecord[]; loading: boolean; error: string; checkedAt: string;
};

function readCollection(value: unknown, kind: string): DomainRecord[] {
  const items = value && typeof value === 'object' ? (value as { items?: unknown }).items : null;
  if (!Array.isArray(items) || !items.every(item => item && typeof item === 'object'
    && typeof item.id === 'string' && item.id.length > 0 && item.kind === kind
    && typeof item.title === 'string' && typeof item.status === 'string'
    && Number.isInteger(item.version) && item.version > 0
    && item.data && typeof item.data === 'object' && !Array.isArray(item.data))) {
    throw new Error('The saved workflow records response was not valid. Retry loading the records.');
  }
  return items as DomainRecord[];
}

export function useWorkflowContext(token: string, revision: number, contextKey: string) {
  const [attempt, setAttempt] = useState(0);
  const [snapshot, setSnapshot] = useState<Snapshot>(() => ({ token, revision, contextKey, attempt,
    records: [], loading: true, error: '', checkedAt: '' }));
  const reload = useCallback(() => setAttempt(value => value + 1), []);
  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    const scope = { token, revision, contextKey, attempt };
    const commit = (next: Snapshot) => {
      if (active && !controller.signal.aborted) setSnapshot(next);
    };
    commit({ ...scope, records: [], loading: true, error: '', checkedAt: '' });
    Promise.all(contextKinds.map(async kind => readCollection(
      await request<unknown>(`/records/${kind}`, token, { signal: controller.signal }), kind,
    ))).then(groups => {
      const records = groups.flat();
      if (new Set(records.map(record => record.id)).size !== records.length) {
        throw new Error('The saved workflow records response contained duplicate records. Retry loading the records.');
      }
      commit({ ...scope, records, loading: false, error: '', checkedAt: new Date().toISOString() });
    }).catch(cause => {
      commit({ ...scope, records: [], loading: false, error: errorMessage(cause), checkedAt: '' });
    });
    return () => { active = false; controller.abort(); };
  }, [token, revision, contextKey, attempt]);
  const current = snapshot.token === token && snapshot.revision === revision
    && snapshot.contextKey === contextKey && snapshot.attempt === attempt;
  return { records: current ? snapshot.records : [], loading: current ? snapshot.loading : true,
    error: current ? snapshot.error : '', checkedAt: current ? snapshot.checkedAt : '', reload };
}
