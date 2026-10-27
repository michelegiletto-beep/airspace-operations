import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ContractHelp } from './ContractHelp';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it('loads the input contract with the session credential only when requested', async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ contracts: { ScheduleRequest: { title: 'ScheduleRequest', type: 'object', required: ['missions'] } } }))); vi.stubGlobal('fetch', fetch);
  const { container } = render(<ContractHelp token="isolated-token" name="ScheduleRequest" />); expect(fetch).not.toHaveBeenCalled();
  const details = container.querySelector('details')!; details.open = true; fireEvent(details, new Event('toggle'));
  await screen.findByRole('button', { name: 'Download ScheduleRequest schema' });
  expect(fetch).toHaveBeenCalledWith('/api/v1/contracts', expect.objectContaining({ headers: { Authorization: 'Bearer isolated-token' } }));
});
