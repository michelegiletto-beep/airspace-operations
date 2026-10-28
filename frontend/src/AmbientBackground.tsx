import { useEffect, useRef } from 'react';
import { useCompanionMotion } from './useCompanionMotion';

// Fresh application styling, informed by the owner's public pointer-reactive material.
// No proprietary platform stylesheet or trading implementation is copied here.
export function AmbientBackground() {
  const layer = useRef<HTMLDivElement>(null);
  const { motion } = useCompanionMotion();
  useEffect(() => {
    if (!motion) return;
    let frame = 0; let x = 50; let y = 40;
    const update = () => {
      frame = 0;
      layer.current?.style.setProperty('--ambient-x', `${x}%`);
      layer.current?.style.setProperty('--ambient-y', `${y}%`);
    };
    const follow = (event: PointerEvent) => {
      if (document.hidden) return;
      x = Math.max(0,Math.min(100,event.clientX / Math.max(1, window.innerWidth) * 100));
      y = Math.max(0,Math.min(100,event.clientY / Math.max(1, window.innerHeight) * 100));
      if (!frame) frame = requestAnimationFrame(update);
    };
    const focus = (event: FocusEvent) => {
      if (!(event.target instanceof HTMLElement) || document.hidden) return;
      const bounds = event.target.getBoundingClientRect();
      x = Math.max(0,Math.min(100,(bounds.left+bounds.width/2)/Math.max(1,window.innerWidth)*100));
      y = Math.max(0,Math.min(100,(bounds.top+bounds.height/2)/Math.max(1,window.innerHeight)*100));
      if(!frame)frame=requestAnimationFrame(update);
    };
    window.addEventListener('pointermove', follow, { passive: true });
    document.addEventListener('focusin',focus);
    return () => { cancelAnimationFrame(frame); window.removeEventListener('pointermove', follow); document.removeEventListener('focusin',focus); };
  }, [motion]);
  return <div ref={layer} aria-hidden="true" className={`workspace-ambient ${motion ? 'ambient-moving' : ''}`}><span/><span/><span/></div>;
}
