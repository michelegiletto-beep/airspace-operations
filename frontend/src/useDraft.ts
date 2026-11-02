import {useCallback,useEffect,useLayoutEffect,useRef,useState} from 'react';
import type {Dispatch,SetStateAction} from 'react';

function readDraft<T>(key:string,initial:T):T{
 try{
  const stored=sessionStorage.getItem(key);
  if(stored===null)return initial;
  const parsed:unknown=JSON.parse(stored);
  const compatible=initial===null?parsed===null:Array.isArray(initial)?Array.isArray(parsed):
   typeof initial==='object'?Boolean(parsed&&typeof parsed==='object'&&!Array.isArray(parsed)):
   typeof parsed===typeof initial&&(typeof parsed!=='number'||Number.isFinite(parsed));
  return compatible?parsed as T:initial;
 }catch{return initial;}
}

export function useDraftState<T>(key:string,initial:T):[T,Dispatch<SetStateAction<T>>]{
 type Scope={key:string};
 const active=useRef(true);
 const [snapshot,setSnapshot]=useState(()=>({scope:{key} as Scope,value:readDraft(key,initial)}));
 const current=snapshot.scope.key===key?snapshot:{scope:{key},value:readDraft(key,initial)};
 if(current!==snapshot)setSnapshot(current);
 const scope=current.scope;
 useLayoutEffect(()=>{active.current=true;return()=>{active.current=false;};},[]);
 useEffect(()=>{
  try{sessionStorage.setItem(scope.key,JSON.stringify(current.value));}
  catch{/* Full session storage must not discard the in-memory draft. */}
 },[scope,current.value]);
 const setValue=useCallback<Dispatch<SetStateAction<T>>>(next=>{
  if(!active.current)return;
  setSnapshot(previous=>{
   if(!active.current||previous.scope!==scope)return previous;
   return {scope,value:typeof next==='function'?(next as (value:T)=>T)(previous.value):next};
  });
 },[scope]);
 return[current.value,setValue];
}
export function clearDraft(prefix:string){for(const key of Object.keys(sessionStorage))if(key.startsWith(prefix))sessionStorage.removeItem(key);}
