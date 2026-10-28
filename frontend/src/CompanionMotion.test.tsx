import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AgentCompanion } from './AgentCompanion';
import { CompanionArtwork } from './CompanionArtwork';
import { AmbientBackground } from './AmbientBackground';
import { loadCompanionRuntime } from './companionRuntime';
import type { CompanionHandle } from './companionRuntime';

vi.mock('./companionRuntime', () => ({ loadCompanionRuntime: vi.fn() }));
const load = vi.mocked(loadCompanionRuntime);
beforeEach(() => { localStorage.clear(); load.mockReset(); });
afterEach(() => { cleanup(); localStorage.clear(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('companion motion preferences and interactions', () => {
  it('keeps the fallback animated until the user explicitly pauses it', async () => {
    load.mockRejectedValue(new Error('Isolated renderer outage'));
    const view = render(<AgentCompanion label="Isolated companion"/>);
    await waitFor(() => expect(view.container.querySelector('canvas')?.dataset.companionRuntime).toBe('fallback'));
    expect(view.container.querySelector('svg')?.getAttribute('data-motion')).toBe('animated');
    expect(view.container.querySelector('img')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Pause companion animation' }));
    expect(view.container.querySelector('svg')?.getAttribute('data-motion')).toBe('paused');
    fireEvent.click(screen.getByRole('button', { name: 'Enable companion animation' }));
    expect(view.container.querySelector('svg')?.getAttribute('data-motion')).toBe('animated');
  });

  it('does not let the motion button override the operating-system reduced-motion preference', async () => {
    vi.stubGlobal('matchMedia', vi.fn(() => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() })));
    load.mockRejectedValue(new Error('Isolated renderer outage'));
    const view = render(<AgentCompanion label="Isolated reduced-motion fallback"/>);
    const button = screen.getByRole('button', { name: 'Animation follows reduced-motion setting' }) as HTMLButtonElement;
    expect(button.disabled).toBe(true); fireEvent.click(button);
    await waitFor(() => expect(view.container.querySelector('canvas')?.dataset.companionRuntime).toBe('fallback'));
    expect(view.container.querySelector('svg')?.getAttribute('data-motion')).toBe('paused');
  });

  it('honours global pause even when browser preference storage is unavailable', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('Isolated storage denial'); });
    load.mockRejectedValue(new Error('Isolated renderer outage'));
    const view = render(<><AgentCompanion label="First companion"/><AgentCompanion compact label="Second companion"/><AmbientBackground/></>);
    fireEvent.click(screen.getByRole('button', { name: 'Pause companion animation' }));
    expect(view.container.querySelector('.ambient-moving')).toBeNull();
    for (const svg of view.container.querySelectorAll('.companion-procedural')) expect(svg.getAttribute('data-motion')).toBe('paused');
  });

  it('forwards explicit gestures and keyboard focus to the owned runtime', async () => {
    const handle: CompanionHandle = { ready: Promise.resolve({ isolatedImage: true }), setState: vi.fn(), setPreferences: vi.fn(), diagnostics: () => ({ engine: 'webgl-mesh-2.5d' }), destroy: vi.fn(), trigger: vi.fn() };
    load.mockResolvedValue({ mountMascot: () => handle });
    const view = render(<CompanionArtwork state="idle" appearance="indigo" motion gesture={{ name: 'soft', sequence: 0 }}/>);
    await waitFor(() => expect(view.container.querySelector('canvas')?.dataset.companionRuntime).toBe('active'));
    view.rerender(<CompanionArtwork state="idle" appearance="indigo" motion gesture={{ name: 'ack', sequence: 1 }}/>);
    expect(handle.trigger).toHaveBeenCalledWith('ack', 1400);
    fireEvent.focusIn(document.body);
    expect(handle.trigger).toHaveBeenCalledWith('question', 1000, 5);
    view.unmount(); expect(handle.destroy).toHaveBeenCalledOnce();
  });

  it('bounds pointer following and cancels pending frames when the companion unmounts', async () => {
    let draw!: FrameRequestCallback;
    vi.stubGlobal('requestAnimationFrame', vi.fn((callback: FrameRequestCallback) => { draw = callback; return 44; }));
    const cancel = vi.fn(); vi.stubGlobal('cancelAnimationFrame', cancel);
    load.mockRejectedValue(new Error('Isolated renderer outage'));
    const view = render(<CompanionArtwork state="idle" appearance="coral" motion/>);
    act(() => { window.dispatchEvent(new MouseEvent('pointermove', { clientX: window.innerWidth * 4, clientY: window.innerHeight * 4 })); draw(0); });
    const surface = view.container.querySelector('.companion-surface') as HTMLElement;
    expect(surface.style.getPropertyValue('--companion-follow-x')).toBe('4px');
    expect(surface.style.getPropertyValue('--companion-follow-y')).toBe('3px');
    act(() => window.dispatchEvent(new MouseEvent('pointermove', { clientX: 0, clientY: 0 })));
    view.unmount(); expect(cancel).toHaveBeenCalledWith(44);
  });

  it('bounds reactive background updates and removes pointer handling when paused', () => {
    let draw!: FrameRequestCallback;
    const frame = vi.fn((callback: FrameRequestCallback) => { draw = callback; return 51; });
    vi.stubGlobal('requestAnimationFrame', frame); vi.stubGlobal('cancelAnimationFrame', vi.fn());
    const view = render(<><AmbientBackground/><button>Isolated focus target</button></>);
    act(() => { window.dispatchEvent(new MouseEvent('pointermove', { clientX: window.innerWidth / 2, clientY: window.innerHeight / 2 })); draw(0); });
    const layer = view.container.firstChild as HTMLElement;
    expect(layer.style.getPropertyValue('--ambient-x')).toBe('50%');
    const focusTarget=screen.getByRole('button',{name:'Isolated focus target'});
    vi.spyOn(focusTarget,'getBoundingClientRect').mockReturnValue(new DOMRect(window.innerWidth/4,window.innerHeight/4,0,0));
    act(()=>{fireEvent.focusIn(focusTarget);draw(0);});
    expect(layer.style.getPropertyValue('--ambient-x')).toBe('25%');
    act(() => window.dispatchEvent(new CustomEvent('sl-companion-motion', { detail: false })));
    frame.mockClear();
    act(() => window.dispatchEvent(new MouseEvent('pointermove', { clientX: 1, clientY: 1 })));
    expect(frame).not.toHaveBeenCalled(); expect(layer.className).not.toContain('ambient-moving');
  });
});
