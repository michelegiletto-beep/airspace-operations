import {createElement,StrictMode,Suspense,startTransition,useState} from 'react';
import {act,cleanup,fireEvent,render,renderHook,screen} from '@testing-library/react';
import {afterEach,describe,expect,it,vi} from 'vitest';
import {useDraftState} from './useDraft';

afterEach(()=>{cleanup();sessionStorage.clear();vi.restoreAllMocks();});

describe('draft storage boundaries',()=>{
 it('keeps the committed draft editable when another key render suspends without committing',async()=>{
  const forever=new Promise<void>(()=>{});let setKey!:(key:string)=>void;
  function Draft({keyName}:{keyName:string}){
   const [value,setValue]=useDraftState(keyName,'');
   if(keyName==='B')throw forever;
   return createElement('input',{'aria-label':'Isolated draft',value,onChange:(event:{target:{value:string}})=>setValue(event.target.value)});
  }
  function App(){const [key,change]=useState('A');setKey=change;return createElement(Suspense,{fallback:createElement('p',null,'Loading B')},createElement(Draft,{keyName:key}));}
  render(createElement(App));
  fireEvent.change(screen.getByLabelText('Isolated draft'),{target:{value:'A before'}});
  await act(async()=>{startTransition(()=>setKey('B'));});
  fireEvent.change(screen.getByLabelText('Isolated draft'),{target:{value:'A after'}});
  expect((screen.getByLabelText('Isolated draft') as HTMLInputElement).value).toBe('A after');
  expect(JSON.parse(sessionStorage.getItem('A')!)).toBe('A after');
  expect(sessionStorage.getItem('B')).toBeNull();
 });

 it('preserves functional updates during StrictMode effect replay',()=>{
  const hook=renderHook(()=>useDraftState('isolated:strict','Before'),{wrapper:({children})=>createElement(StrictMode,null,children)});
  act(()=>hook.result.current[1](value=>value+' after'));
  expect(hook.result.current[0]).toBe('Before after');
  expect(JSON.parse(sessionStorage.getItem('isolated:strict')!)).toBe('Before after');
 });
 it('switches keys without showing or persisting the previous actor draft',()=>{
  sessionStorage.setItem('isolated:actor-a',JSON.stringify('Actor A draft'));
  sessionStorage.setItem('isolated:actor-b',JSON.stringify('Actor B draft'));
  const frames:string[]=[];
  const hook=renderHook(({key})=>{const draft=useDraftState(key,'');frames.push(draft[0]);return draft;},{initialProps:{key:'isolated:actor-a'}});
  frames.length=0;hook.rerender({key:'isolated:actor-b'});
  expect(frames.length).toBeGreaterThan(0);
  expect(frames.every(value=>value==='Actor B draft')).toBe(true);
  expect(hook.result.current[0]).toBe('Actor B draft');
  expect(JSON.parse(sessionStorage.getItem('isolated:actor-a')!)).toBe('Actor A draft');
  expect(JSON.parse(sessionStorage.getItem('isolated:actor-b')!)).toBe('Actor B draft');
 });

 it('rejects stale direct and functional setters through A to B to A transitions',()=>{
  sessionStorage.setItem('isolated:a',JSON.stringify('A'));
  sessionStorage.setItem('isolated:b',JSON.stringify('B'));
  const hook=renderHook(({key})=>useDraftState(key,''),{initialProps:{key:'isolated:a'}});
  const firstA=hook.result.current[1];hook.rerender({key:'isolated:b'});
  const oldB=hook.result.current[1];hook.rerender({key:'isolated:a'});
  const late=vi.fn(()=> 'Late private draft');
  act(()=>{firstA('Late actor A');oldB(late);});
  expect(late).not.toHaveBeenCalled();
  expect(hook.result.current[0]).toBe('A');
  expect(JSON.parse(sessionStorage.getItem('isolated:b')!)).toBe('B');
  act(()=>hook.result.current[1](value=>value+' current'));
  expect(hook.result.current[0]).toBe('A current');
  expect(JSON.parse(sessionStorage.getItem('isolated:a')!)).toBe('A current');
 });

 it('preserves the current draft and functional updates on same-key rerenders',()=>{
  const hook=renderHook(({initial})=>useDraftState('isolated:same',initial),{initialProps:{initial:'Initial'}});
  act(()=>hook.result.current[1](value=>value+' edited'));
  hook.rerender({initial:'A new default'});
  expect(hook.result.current[0]).toBe('Initial edited');
  expect(JSON.parse(sessionStorage.getItem('isolated:same')!)).toBe('Initial edited');
 });

 it.each(['{','null','{}','[]','42','false'])('falls back when stored string data is malformed or incompatible: %s',stored=>{
  sessionStorage.setItem('isolated:invalid',stored);
  const hook=renderHook(()=>useDraftState('isolated:invalid','Safe default'));
  expect(hook.result.current[0]).toBe('Safe default');
 });

 it('restores array, object and false boolean drafts without sharing keys',()=>{
  sessionStorage.setItem('isolated:array',JSON.stringify(['saved']));
  sessionStorage.setItem('isolated:object',JSON.stringify({title:'Saved'}));
  sessionStorage.setItem('isolated:boolean','false');
  expect(renderHook(()=>useDraftState<string[]>('isolated:array',[])).result.current[0]).toEqual(['saved']);
  expect(renderHook(()=>useDraftState('isolated:object',{title:''})).result.current[0]).toEqual({title:'Saved'});
  expect(renderHook(()=>useDraftState('isolated:boolean',true)).result.current[0]).toBe(false);
 });

 it('keeps an in-memory draft when storage is unavailable and starts another key safely',()=>{
  vi.spyOn(Storage.prototype,'getItem').mockImplementation(()=>{throw new Error('Isolated storage read denial');});
  vi.spyOn(Storage.prototype,'setItem').mockImplementation(()=>{throw new Error('Isolated storage quota');});
  const hook=renderHook(({key})=>useDraftState(key,'Default'),{initialProps:{key:'isolated:a'}});
  act(()=>hook.result.current[1]('Unsaved actor A draft'));
  expect(hook.result.current[0]).toBe('Unsaved actor A draft');
  hook.rerender({key:'isolated:b'});
  expect(hook.result.current[0]).toBe('Default');
 });

 it('ignores a setter after unmount without executing a functional update',()=>{
  const hook=renderHook(()=>useDraftState('isolated:unmount','Before'));
  const setter=hook.result.current[1];hook.unmount();const late=vi.fn(()=> 'After');
  act(()=>setter(late));expect(late).not.toHaveBeenCalled();
  expect(JSON.parse(sessionStorage.getItem('isolated:unmount')!)).toBe('Before');
 });
});
