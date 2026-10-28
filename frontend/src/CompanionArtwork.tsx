import { useEffect, useId, useRef, useState } from 'react';
import { loadCompanionRuntime } from './companionRuntime';
import type { CompanionHandle, CompanionHealth } from './companionRuntime';

export type CompanionState = 'idle' | 'running' | 'paused' | 'attention' | 'unavailable';
export type CompanionAppearance = 'indigo' | 'coral';
export type CompanionGesture = { name: 'soft' | 'ack' | 'question' | 'send' | 'uncertain' | 'settle'; sequence: number };
const health: Record<CompanionState, CompanionHealth> = {
  idle: 'alive', running: 'scanning', paused: 'paused', attention: 'stale', unavailable: 'disconnected',
};

export function CompanionArtwork({ state, appearance, motion, gesture }: {
  state: CompanionState; appearance: CompanionAppearance; motion: boolean; gesture?: CompanionGesture;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const surface = useRef<HTMLSpanElement>(null);
  const handle = useRef<CompanionHandle | null>(null);
  const latest = useRef({ state, motion });
  latest.current = { state, motion };
  const [status, setStatus] = useState<'loading' | 'active' | 'fallback'>('loading');
  const [engine, setEngine] = useState('');
  const gradient = useId().replaceAll(':', '');

  useEffect(() => {
    let cancelled = false;
    let failed = false;
    let destroyed = false;
    let instance: CompanionHandle | null = null;
    setStatus('loading'); setEngine('');
    function destroy() {
      if (instance && !destroyed) { destroyed = true; instance.destroy(); }
    }
    function fallback() {
      if (cancelled || failed) return;
      failed = true;
      destroy();
      if (handle.current === instance) handle.current = null;
      setEngine('procedural-css'); setStatus('fallback');
    }
    async function mount() {
      try {
        const runtime = await loadCompanionRuntime();
        if (cancelled || !canvas.current) return;
        instance = runtime.mountMascot(canvas.current, {
          mascotId: appearance === 'coral' ? 'mascot-06' : 'mascot-01',
          appearanceSeed: appearance === 'coral' ? 2292 : 137,
          state: health[latest.current.state], motion: latest.current.motion ? 'full' : 'off',
          autoReduceMotion: false, visible: true,
          label: `${appearance === 'coral' ? 'Coral' : 'Indigo'}, System Lab workflow companion`,
          onError: fallback,
        });
        handle.current = instance;
        if (failed) { destroy(); handle.current = null; return; }
        const image = await instance.ready;
        if (cancelled) return;
        if (failed || !image) { fallback(); return; }
        const actualEngine = instance.diagnostics().engine;
        if (!['webgl-mesh-2.5d', 'canvas2d-deformation'].includes(String(actualEngine))) { fallback(); return; }
        instance.setState(health[latest.current.state]);
        instance.setPreferences({ motion: latest.current.motion ? 'full' : 'off', autoReduceMotion: false });
        setEngine(String(actualEngine)); setStatus('active');
      } catch { fallback(); }
    }
    void mount();
    const observer = typeof MutationObserver === 'function' && canvas.current
      ? new MutationObserver(() => {
        const actualEngine = canvas.current?.dataset.mascotEngine;
        if (!cancelled && !failed && actualEngine) setEngine(actualEngine);
      }) : null;
    if (canvas.current) observer?.observe(canvas.current, { attributes: true, attributeFilter: ['data-mascot-engine'] });
    return () => {
      cancelled = true; observer?.disconnect(); destroy();
      if (handle.current === instance) handle.current = null;
    };
  }, [appearance]);

  useEffect(() => {
    handle.current?.setState(health[state]);
    handle.current?.setPreferences({ motion: motion ? 'full' : 'off', autoReduceMotion: false });
    if (motion) handle.current?.trigger?.(state === 'attention' ? 'question' : state === 'running' ? 'send' : 'settle', 1600);
  }, [state, motion]);

  useEffect(() => {
    if (motion && gesture) handle.current?.trigger?.(gesture.name, 1400);
  }, [gesture?.sequence, gesture?.name, motion]);

  useEffect(() => {
    let frame = 0;
    let x = 0; let y = 0;
    const target = surface.current;
    if (!motion || !target) {
      target?.style.setProperty('--companion-follow-x', '0px');
      target?.style.setProperty('--companion-follow-y', '0px');
      return;
    }
    function draw() {
      frame = 0;
      target?.style.setProperty('--companion-follow-x', `${x * 4}px`);
      target?.style.setProperty('--companion-follow-y', `${y * 3}px`);
    }
    function follow(event: PointerEvent) {
      x = Math.max(-1, Math.min(1, event.clientX / Math.max(1, window.innerWidth) * 2 - 1));
      y = Math.max(-1, Math.min(1, event.clientY / Math.max(1, window.innerHeight) * 2 - 1));
      if (!frame) frame = requestAnimationFrame(draw);
    }
    function focus() { handle.current?.trigger?.('question', 1000, 5); }
    window.addEventListener('pointermove', follow, { passive: true });
    document.addEventListener('focusin', focus);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('pointermove', follow);
      document.removeEventListener('focusin', focus);
    };
  }, [motion]);

  const fallbackVisible = status !== 'active';
  const simpleAnimation = status === 'fallback' || engine === 'canvas2d-deformation';
  return <span ref={surface} className={`companion-surface ${appearance} ${motion ? 'motion-enabled' : 'motion-paused'}`}
    role="img" aria-label={`${appearance === 'indigo' ? 'Indigo' : 'Coral'}, animated System Lab companion${motion ? '' : ', animation paused'}`}>
    <svg className="companion-procedural" data-visible={fallbackVisible} data-motion={motion ? 'animated' : 'paused'} viewBox="0 0 120 120" aria-hidden="true">
      <defs><radialGradient id={gradient}><stop offset="0" stopColor={appearance === 'coral' ? '#ffd0a8' : '#a8e7ff'}/><stop offset=".45" stopColor={appearance === 'coral' ? '#eb755a' : '#5a8ce8'}/><stop offset="1" stopColor={appearance === 'coral' ? '#973d51' : '#443e92'}/></radialGradient></defs>
      <g className="companion-organism"><ellipse className="companion-body" cx="60" cy="62" rx="36" ry="37" fill={`url(#${gradient})`}/>
        {[0, 1, 2, 3, 4].map(index => <g className={`companion-fold fold-${index}`} key={index}><path d={`M ${29 + index * 5} 51 C ${33 + index * 3} ${13 + index * 4}, ${93 - index * 4} ${20 + index * 3}, ${86 - index * 3} 69 C ${84 - index * 5} 104, ${34 + index * 5} 98, ${29 + index * 5} 51`} fill="none" stroke={appearance === 'coral' ? '#ffe3b7' : '#b5dffa'} strokeWidth="2.6" opacity={.28 + index * .05}/></g>)}
        <ellipse className="companion-light" cx="48" cy="45" rx="14" ry="19" fill="#eefaff" opacity=".18"/>
      </g>
    </svg>
    <canvas ref={canvas} aria-hidden="true" className="owned-companion-canvas" data-companion-runtime={status} data-companion-engine={engine}/>
    {simpleAnimation ? <span className="companion-renderer-status" title={status === 'fallback' ? 'The owned renderer is unavailable. Procedural animation is active.' : 'WebGL is unavailable. The owned 2D animation is active.'}>2D<span className="sr-only"> animation. {status === 'fallback' ? 'The owned renderer is unavailable.' : 'WebGL is unavailable.'}</span></span> : null}
  </span>;
}
