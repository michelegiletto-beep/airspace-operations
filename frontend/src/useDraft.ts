import {useEffect,useState} from 'react';
import type {Dispatch,SetStateAction} from 'react';
export function useDraftState<T>(key:string,initial:T):[T,Dispatch<SetStateAction<T>>]{
 const [value,setValue]=useState<T>(()=>{try{const stored=sessionStorage.getItem(key);return stored?JSON.parse(stored) as T:initial;}catch{return initial;}});
 useEffect(()=>{try{sessionStorage.setItem(key,JSON.stringify(value));}catch{/* Full session storage must not discard the in-memory draft. */}},[key,value]);
 return[value,setValue];
}
export function clearDraft(prefix:string){for(const key of Object.keys(sessionStorage))if(key.startsWith(prefix))sessionStorage.removeItem(key);}
