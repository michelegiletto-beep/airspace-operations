import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import App from './App';
import { workspaces } from './schema';

vi.mock('./companionRuntime', () => ({ loadCompanionRuntime: vi.fn().mockRejectedValue(new Error('Isolated renderer outage')) }));
afterEach(() => { cleanup(); sessionStorage.clear(); localStorage.clear(); vi.unstubAllGlobals(); });

it('renders every empty authenticated workspace and keeps the assistant alongside the application', async () => {
  history.replaceState(null, '', '#operations');
  const user = { id: 'isolated-user', email: 'review@example.invalid', role: 'regulatory', organisation_id: 'isolated-org' };
  sessionStorage.setItem('sl-airspace-session-v1', JSON.stringify({ token: 'isolated-token', user }));
  const fetcher = vi.fn(async (path: string) => {
    let value: unknown = { items: [] };
    if (path === '/api/v1/me') value = user;
    else if (path === '/map/europe.geojson') value = { type: 'FeatureCollection', features: [] };
    else if (path === '/api/v1/agent-capabilities') value = { task_roles: {}, tools: [] };
    else if (path === '/api/v1/contracts') value = { contracts: {} };
    else if (path === '/api/v1/companion/catalog') value = { workspaces: [], action_kinds: [], model_status: { state: 'Not Installed', message: 'Isolated local model is unavailable.' } };
    return new Response(JSON.stringify(value));
  });
  vi.stubGlobal('fetch', fetcher);
  const view = render(<App/>);
  for (const workspace of workspaces) {
    await screen.findByRole('button', { name: workspace.label });
    fireEvent.click(screen.getByRole('button', { name: workspace.label }));
    expect(await screen.findByRole('heading', { level: 1, name: workspace.label })).toBeTruthy();
    expect(view.container.querySelector('.eyebrow')).toBeNull();
  }
  fireEvent.click(screen.getByRole('button', { name: 'Ask Indigo' }));
  expect(await screen.findByLabelText('Your request')).toBeTruthy();
  expect(screen.getByRole('heading', { level: 1, name: 'Administration' })).toBeTruthy();
  expect(view.container.querySelector('img[src*="mascots/"]')).toBeNull();
  expect(fetcher.mock.calls.every(([path]) => path.startsWith('/api/v1/') || path === '/map/europe.geojson')).toBe(true);
});

it('lets a signed-out user pause the companion and background without losing entered form data', async()=>{
  const fetcher=vi.fn();vi.stubGlobal('fetch',fetcher);
  const view=render(<App/>);
  expect(screen.getByRole('heading',{name:'Sign in to your workspace'})).toBeTruthy();
  fireEvent.change(screen.getByLabelText('Email'),{target:{value:'isolated@example.invalid'}});
  fireEvent.click(screen.getByRole('button',{name:'Pause companion animation'}));
  expect(view.container.querySelector('.ambient-moving')).toBeNull();
  expect(view.container.querySelector('.companion-procedural')?.getAttribute('data-motion')).toBe('paused');
  expect((screen.getByLabelText('Email') as HTMLInputElement).value).toBe('isolated@example.invalid');
  expect(fetcher).not.toHaveBeenCalled();
});
