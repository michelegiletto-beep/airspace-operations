export type CompanionHealth='alive'|'scanning'|'paused'|'disconnected'|'stale'|'unknown'|'error'|'reconciling';
export interface CompanionPreferences {motion:'full'|'off';autoReduceMotion:false}
export interface CompanionHandle {
 ready:Promise<unknown|null>;
 setState(state:CompanionHealth):void;
 setPreferences(preferences:CompanionPreferences):void;
 trigger?(gesture:'soft'|'ack'|'question'|'send'|'uncertain'|'settle',durationMs?:number,priority?:number):void;
 diagnostics():{engine?:string;[key:string]:unknown};
 destroy():void;
}
export interface CompanionRuntime {
 mountMascot(canvas:HTMLCanvasElement,options:CompanionPreferences&{mascotId:'mascot-01'|'mascot-06';appearanceSeed:number;state:CompanionHealth;visible:true;label:string;onError:(error:Error)=>void}):CompanionHandle;
}
const runtimeUrl='/vendor/systemlab-companion/mascot-renderer.mjs';
let pending:Promise<CompanionRuntime>|null=null;
export function loadCompanionRuntime():Promise<CompanionRuntime>{
 if(!pending)pending=import(/* @vite-ignore */ runtimeUrl).then((module:unknown)=>{if(!module||typeof(module as CompanionRuntime).mountMascot!=='function')throw new Error('The owned presentation renderer is unavailable.');return module as CompanionRuntime;}).catch(error=>{pending=null;throw error;});
 return pending;
}
