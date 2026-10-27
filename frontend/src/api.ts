export interface User { id: string; email: string; role: string; organisation_id: string }
export interface Session { token: string; user: User }
export interface DomainRecord {
  id: string; kind: string; title: string; status: string; data: Record<string, unknown>;
  version: number; created_at: string; updated_at: string; created_by: string;
}
export interface Collection<T> { items: T[]; total?: number }
export class ApiError extends Error {
  constructor(public readonly status: number, message: string) { super(message); this.name = 'ApiError'; }
}
export function errorMessage(error: unknown): string { return error instanceof Error ? error.message : 'The request could not be completed.'; }
export function parseObject(value: string): Record<string, unknown> {
  const parsed: unknown = JSON.parse(value);
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('Record data must be a JSON object.');
  return parsed as Record<string, unknown>;
}
export function writableData(data: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(data).filter(([key]) => !key.startsWith('_') && key !== 'independent_second_reviewer'));
}
export async function request<T>(path: string, token: string | null, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    cache: 'no-store', ...init, headers: { ...(init.body ? { 'Content-Type': 'application/json' } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init.headers },
  });
  if (!response.ok) {
    let detail = response.statusText || 'Request failed';
    try { const result = await response.json() as { detail?: unknown }; detail = typeof result.detail === 'string' ? result.detail : JSON.stringify(result.detail ?? result); } catch { /* HTTP status remains available. */ }
    throw new ApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a'); link.href = url; link.download = filename; link.click();
  URL.revokeObjectURL(url);
}
export async function downloadFile(path: string, token: string, filename: string): Promise<void> {
  const response = await fetch(`/api/v1${path}`, { cache: 'no-store', headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) {
    let message = 'The file could not be downloaded.';
    try { const body = await response.json() as { detail?: unknown }; if (typeof body.detail === 'string') message = body.detail; } catch { /* The HTTP status is retained. */ }
    throw new ApiError(response.status, message);
  }
  saveBlob(await response.blob(), filename);
}
export async function downloadPackage(id: string, token: string, format: 'json' | 'html' = 'json'): Promise<void> {
  await downloadFile(`/records/case/${encodeURIComponent(id)}/export?format=${format}`, token, `case-${id}.${format}`);
}
export function fileToBase64(file: File): Promise<string> {
  if (file.size === 0 || file.size > 1_000_000) return Promise.reject(new Error('Select a non-empty evidence file up to 1 MB (1,000,000 bytes).'));
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('The selected file could not be read.'));
    reader.onload = () => { const result = reader.result; if (typeof result !== 'string' || !result.includes(',')) reject(new Error('The evidence file could not be encoded.')); else resolve(result.slice(result.indexOf(',') + 1)); };
    reader.readAsDataURL(file);
  });
}
export function displayDate(value: unknown): string {
  if (typeof value !== 'string' || !value) return 'Not recorded';
  const date = new Date(value); return Number.isNaN(date.getTime()) ? value : `${date.toISOString().replace('T', ' ').slice(0, 19)} UTC`;
}
