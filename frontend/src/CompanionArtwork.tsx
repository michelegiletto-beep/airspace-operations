import {useEffect,useRef,useState} from 'react';
import {loadCompanionRuntime} from './companionRuntime';
import type {CompanionHandle,CompanionHealth} from './companionRuntime';
export type CompanionState='idle'|'running'|'paused'|'attention'|'unavailable';
export type CompanionAppearance='indigo'|'coral';
const health:Record<CompanionState,CompanionHealth>={idle:'alive',running:'scanning',paused:'paused',attention:'stale',unavailable:'disconnected'};
export function CompanionArtwork({state,appearance,motion}:{state:CompanionState;appearance:CompanionAppearance;motion:boolean}){
 const canvas=useRef<HTMLCanvasElement>(null);const handle=useRef<CompanionHandle|null>(null);const latest=useRef({state,motion});latest.current={state,motion};
 const [status,setStatus]=useState<'loading'|'active'|'fallback'>('loading');const [engine,setEngine]=useState('');
 useEffect(()=>{
  let cancelled=false;let failed=false;let instance:CompanionHandle|null=null;setStatus('loading');setEngine('');
  function fallback(){if(cancelled)return;failed=true;instance?.destroy();if(handle.current===instance)handle.current=null;setStatus('fallback');}
  async function mount(){try{
   const runtime=await loadCompanionRuntime();if(cancelled||!canvas.current)return;
   instance=runtime.mountMascot(canvas.current,{mascotId:appearance==='coral'?'mascot-06':'mascot-01',appearanceSeed:appearance==='coral'?2292:137,state:health[latest.current.state],motion:latest.current.motion?'full':'off',autoReduceMotion:false,visible:true,label:`${appearance==='coral'?'Coral':'Indigo'}, System Lab workflow companion`,onError:fallback});
   handle.current=instance;if(failed){instance.destroy();handle.current=null;return;}
   if(instance.diagnostics().engine!=='webgl-mesh-2.5d'){fallback();return;}
   const image=await instance.ready;if(cancelled)return;
   if(failed||!image||instance.diagnostics().engine!=='webgl-mesh-2.5d'){fallback();return;}
   instance.setState(health[latest.current.state]);instance.setPreferences({motion:latest.current.motion?'full':'off',autoReduceMotion:false});setEngine(String(instance.diagnostics().engine??''));setStatus('active');
  }catch{fallback();}}
  void mount();return()=>{cancelled=true;instance?.destroy();if(handle.current===instance)handle.current=null;};
 },[appearance]);
 useEffect(()=>{handle.current?.setState(health[state]);handle.current?.setPreferences({motion:motion?'full':'off',autoReduceMotion:false});},[state,motion]);
 return <><img className={status==='active'?'runtime-image-replaced':''} src={`/mascots/${appearance}.webp`} alt={`${appearance==='indigo'?'Indigo':'Coral'}, System Lab workflow companion`} width={360} height={360}/><canvas ref={canvas} aria-hidden="true" className="owned-companion-canvas" data-companion-runtime={status} data-companion-engine={engine}/></>;
}
