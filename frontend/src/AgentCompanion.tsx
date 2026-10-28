import { Icon } from './Icons';
import {CompanionArtwork} from './CompanionArtwork';
import type {CompanionGesture} from './CompanionArtwork';
import {useCompanionMotion} from './useCompanionMotion';
export function AgentCompanion({ state = 'idle', appearance = 'indigo', compact = false, label, children,gesture }: { state?: 'idle' | 'running' | 'paused' | 'attention' | 'unavailable'; appearance?: 'indigo' | 'coral'; compact?: boolean; label: string; children?: React.ReactNode;gesture?:CompanionGesture }) {
 const {motion,reduced,toggle}=useCompanionMotion();
 return <div className={`agent-companion companion-${state} ${compact ? 'companion-compact' : ''} ${motion ? 'companion-motion' : ''}`}><div className="companion-art"><CompanionArtwork state={state} appearance={appearance} motion={motion} gesture={gesture}/><span className="companion-state-dot"/></div><div className="companion-copy"><span className="companion-state-label">{state === 'running' ? 'Working' : state === 'paused' ? 'Task paused' : state === 'attention' ? 'Needs attention' : state === 'unavailable' ? 'Model response unavailable' : 'Waiting for input'}</span><strong>{label}</strong>{children}</div>{!compact ? <button type="button" className="companion-motion-button" onClick={toggle} disabled={reduced} aria-pressed={motion} aria-label={reduced?'Animation follows reduced-motion setting':motion ? 'Pause companion animation' : 'Enable companion animation'}><Icon name={motion ? 'pause' : 'play'} size={12}/>{reduced?'Reduced motion':motion ? 'Pause motion' : 'Resume motion'}</button> : null}</div>;
}
