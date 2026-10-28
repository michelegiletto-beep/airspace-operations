import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, displayDate, downloadPackage, fileToBase64, parseObject, request, writableData } from './api';

afterEach(() => vi.unstubAllGlobals());
describe('authenticated API boundary', () => {
  it('sends the bearer credential and JSON body to the versioned service', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 'actual-server-response' }), { status: 200, headers: { 'Content-Type': 'application/json' } }));
    vi.stubGlobal('fetch', fetch);
    const result = await request('/records/case', 'isolated-test-token', { method: 'POST', body: JSON.stringify({ title: 'Isolated software test' }) });
    expect(result).toEqual({ id: 'actual-server-response' });
    expect(fetch).toHaveBeenCalledWith('/api/v1/records/case', expect.objectContaining({ headers: { Authorization: 'Bearer isolated-test-token', 'Content-Type': 'application/json' } }));
  });
  it('preserves a server concurrency rejection rather than reporting success', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Revision conflict: refresh the record' }), { status: 409 })));
    await expect(request('/records/case/test', 'isolated-test-token', { method: 'PUT' })).rejects.toMatchObject({ status: 409, message: 'Revision conflict: refresh the record' });
  });
  it('does not invent a missing error body', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('unavailable', { status: 503, statusText: 'Service Unavailable' })));
    await expect(request('/sources', 'isolated-test-token')).rejects.toBeInstanceOf(ApiError);
  });
  it('shows field validation messages without echoing sensitive submitted values', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: [{ loc: ['body', 'operation_date'], msg: 'Field required', input: 'isolated-private-input' }] }), { status: 422 })));
    await expect(request('/companion/conversations/test/messages', 'isolated-test-token', { method: 'POST' })).rejects.toMatchObject({ status: 422, message: 'Operation date: Field required' });
  });
});
describe('data rendering boundaries', () => {
  it('rejects empty and oversized evidence before reading its content', async () => {
    await expect(fileToBase64(new File([], 'empty.txt', { type: 'text/plain' }))).rejects.toThrow('non-empty');
    await expect(fileToBase64(new File(['x'.repeat(1_000_001)], 'oversized.txt', { type: 'text/plain' }))).rejects.toThrow('1 MB');
    expect(await fileToBase64(new File(['verified test content'], 'isolated.txt', { type: 'text/plain' }))).toBe(btoa('verified test content'));
  });
  it('requests controlled HTML as an authenticated file instead of executing it inline', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response('<html>Controlled isolated test export</html>', { status: 200 })); vi.stubGlobal('fetch', fetch);
    const createUrl = vi.fn().mockReturnValue('blob:isolated-test-url');
    const revoke = vi.fn(); vi.stubGlobal('URL', { createObjectURL: createUrl, revokeObjectURL: revoke });
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    await downloadPackage('isolated-case', 'isolated-token', 'html');
    expect(fetch).toHaveBeenCalledWith('/api/v1/records/case/isolated-case/export?format=html', expect.objectContaining({ headers: { Authorization: 'Bearer isolated-token' }, cache: 'no-store' }));
    expect(click).toHaveBeenCalledTimes(1); expect(revoke).toHaveBeenCalledWith('blob:isolated-test-url');
  });
  it('never sends server metadata or client-edited second-review policy as record fields', () => {
    expect(writableData({ title: 'kept', _prepared_by: 'actor', _approvals: [], independent_second_reviewer: false })).toEqual({ title: 'kept' });
  });
  it('rejects arrays and primitive values as editable record data', () => {
    for (const value of ['[]', 'null', 'true', '1', '"string"']) expect(() => parseObject(value)).toThrow('JSON object');
    expect(parseObject('{"missing":null}')).toEqual({ missing: null });
  });
  it('labels missing time and preserves explicit UTC rendering across DST', () => {
    expect(displayDate(undefined)).toBe('Not recorded');
    expect(displayDate('2026-10-25T02:30:00+02:00')).toBe('2026-10-25 00:30:00 UTC');
    expect(displayDate('2026-10-25T02:30:00+01:00')).toBe('2026-10-25 01:30:00 UTC');
  });
});
