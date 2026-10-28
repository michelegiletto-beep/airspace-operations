import { useEffect, useState } from 'react';
import { errorMessage, request } from './api';
import type { Collection, DomainRecord } from './api';
const coreKinds = ['mission','aircraft','personnel','site','route','permission','case','alert','schedule'];
export function useWorkspaceData(token:string, revision=0) {
 const [records,setRecords]=useState<Record<string,DomainRecord[]>>({}); const [loading,setLoading]=useState(true); const [error,setError]=useState(''); const [checkedAt,setCheckedAt]=useState('');
 useEffect(()=>{const controller=new AbortController();setLoading(true);setError('');
  Promise.all(coreKinds.map(async kind=>{const result=await request<Collection<DomainRecord>>(`/records/${kind}`,token,{signal:controller.signal});return [kind,result.items] as const;})).then(results=>{setRecords(Object.fromEntries(results));setCheckedAt(new Date().toISOString());}).catch((cause:unknown)=>{if(!(cause instanceof DOMException&&cause.name==='AbortError'))setError(errorMessage(cause));}).finally(()=>{if(!controller.signal.aborted)setLoading(false);});
  return()=>controller.abort();
 },[token,revision]);
 return {records,loading,error,checkedAt};
}
