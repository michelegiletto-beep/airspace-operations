import {act,cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react';
import {afterEach,describe,expect,it,vi} from 'vitest';
import {AgentWorkspace} from './AgentWorkspace';
import type {User} from './api';

vi.mock('./AgentCompanion',()=>({AgentCompanion:()=>null}));
const actor:User={id:'isolated-planner',email:'planner@example.invalid',role:'planner',organisation_id:'isolated-org'};
const taskRoles={regulatory_research:['regulatory','planner'],authorisation_preparation:['regulatory'],site_assessment:['planner'],scheduling_proposal:['planner'],maintenance_planning:['fleet_manager','planner','reviewer'],cross_border_readiness:['planner'],fleet_sharing_review:['fleet_manager','planner','reviewer']};
const catalogue={task_roles:taskRoles,tools:[]};
const json=(value:unknown,status=200)=>new Response(JSON.stringify(value),{status});
function deferred<T>(){let resolve!:(value:T)=>void;const promise=new Promise<T>(done=>{resolve=done;});return {promise,resolve};}
function install(capability:()=>Promise<Response>,schedules:unknown[]=[]){
 const fetch=vi.fn((path:string,init?:RequestInit)=>{
  if(path==='/api/v1/agent-capabilities')return capability();
  if(path==='/api/v1/records/schedule')return Promise.resolve(json({items:schedules}));
  if(path==='/api/v1/agent-workflows'&&init?.method==='POST')return Promise.resolve(json({id:'isolated-created'}));
  return Promise.resolve(json({items:[]}));
 });vi.stubGlobal('fetch',fetch);return fetch;
}
function view(user=actor,token='isolated-token'){return <AgentWorkspace token={token} user={user} revision={0} changed={()=>undefined}/>;}
function button(label:string){return screen.getByRole('button',{name:new RegExp(label)}) as HTMLButtonElement;}
afterEach(()=>{cleanup();sessionStorage.clear();localStorage.clear();vi.unstubAllGlobals();});

describe('workflow preparation permissions and handoff',()=>{
 it('keeps every preparation disabled while the actual permission response is pending',async()=>{
  const pending=deferred<Response>();const fetch=install(()=>pending.promise);render(view());
  expect(screen.getByRole('status').textContent).toContain('Checking workflow permissions');
  expect(button('Maintenance planning').disabled).toBe(true);expect(button('Regulatory research').disabled).toBe(true);
  fireEvent.click(button('Maintenance planning'));
  expect(screen.queryByLabelText('What do you want to achieve?')).toBeNull();
  expect(fetch.mock.calls.every(([,init])=>!init?.method||init.method==='GET')).toBe(true);
  await act(async()=>pending.resolve(json(catalogue)));
  await waitFor(()=>expect(button('Maintenance planning').disabled).toBe(false));
 });
 it('shows readable, associated role handoff and tool inputs beside disabled controls',async()=>{
  install(()=>Promise.resolve(json(catalogue)));render(view({...actor,role:'regulatory'}));
  await waitFor(()=>expect(screen.queryByText('Checking workflow permissions…')).toBeNull());
  const maintenance=button('Maintenance planning');expect(maintenance.disabled).toBe(true);
  const description=document.getElementById(maintenance.getAttribute('aria-describedby')!);
  expect(description?.textContent).toContain('Your role is regulatory');
  expect(description?.textContent).toContain('fleet manager, planner, reviewer');
  expect(description?.textContent).toContain('assign this work to a permitted colleague');
  expect(maintenance.contains(description)).toBe(false);
  const card=maintenance.closest('article')!;const summary=within(card).getByText('Records needed for the tools');
  summary.focus();expect(document.activeElement).toBe(summary);
  expect(card.textContent).toContain('One record may contain both');
  expect(button('Fleet sharing review').closest('article')?.textContent).toContain('schedule proposal with assignments');
 });
 it('retries only the capability GET after failure and does not create or start work',async()=>{
  let tries=0;const fetch=install(()=>Promise.resolve(++tries===1?json({detail:'Permission lookup unavailable'},503):json(catalogue)));
  render(view());await screen.findByRole('button',{name:'Retry workflow permissions'});
  expect(button('Maintenance planning').disabled).toBe(true);const calls=fetch.mock.calls.length;
  fireEvent.click(screen.getByRole('button',{name:'Retry workflow permissions'}));
  await waitFor(()=>expect(button('Maintenance planning').disabled).toBe(false));
  expect(fetch.mock.calls.slice(calls).map(([path])=>path)).toEqual(['/api/v1/agent-capabilities']);
  expect(fetch.mock.calls.every(([,init])=>!init?.method||init.method==='GET')).toBe(true);
 });
 it.each([undefined,null,['planner',7],{planner:true}].map(roles=>[roles]))('does not substitute a local role list for invalid or missing server roles: %j',async roles=>{
  install(()=>Promise.resolve(json({task_roles:{...taskRoles,maintenance_planning:roles},tools:[]})));
  render(view());await screen.findByRole('button',{name:'Retry workflow permissions'});
  expect(button('Maintenance planning').disabled).toBe(true);
  expect(button('Fleet sharing review').disabled).toBe(false);
 });
 it('keeps an explicit empty permission list disabled without inventing allowed roles',async()=>{
  install(()=>Promise.resolve(json({...catalogue,task_roles:{...taskRoles,maintenance_planning:[]}})));
  render(view());await waitFor(()=>expect(button('Fleet sharing review').disabled).toBe(false));
  expect(button('Maintenance planning').disabled).toBe(true);expect(button('Maintenance planning').closest('article')?.textContent).toContain('No preparation role is available');
 });
 it('honours changed server roles even if a familiar local role would previously have been allowed',async()=>{
  install(()=>Promise.resolve(json({...catalogue,task_roles:{...taskRoles,maintenance_planning:['reviewer']}})));
  render(view());await waitFor(()=>expect(button('Fleet sharing review').disabled).toBe(false));
  expect(button('Maintenance planning').disabled).toBe(true);
  expect(button('Maintenance planning').closest('article')?.textContent).toContain('Preparation requires one of these roles: reviewer');
 });
 it('retires an open planner on actor change and ignores an old actor permission response',async()=>{
  const old=deferred<Response>();let calls=0;
  install(()=>++calls===1?Promise.resolve(json(catalogue)):calls===2?old.promise:Promise.resolve(json({...catalogue,task_roles:{...taskRoles,maintenance_planning:['reviewer']}})));
  const mounted=render(view());await waitFor(()=>expect(button('Maintenance planning').disabled).toBe(false));
  fireEvent.click(button('Maintenance planning'));fireEvent.change(screen.getByLabelText('What do you want to achieve?'),{target:{value:'Private unsent planning draft'}});
  mounted.rerender(view({...actor,id:'isolated-second'}));
  expect(screen.queryByLabelText('What do you want to achieve?')).toBeNull();expect(button('Maintenance planning').disabled).toBe(true);
  mounted.rerender(view({...actor,id:'isolated-third'}));
  await waitFor(()=>expect(button('Fleet sharing review').disabled).toBe(false));
  await act(async()=>old.resolve(json(catalogue)));
  expect(button('Maintenance planning').disabled).toBe(true);expect(screen.queryByText('Private unsent planning draft')).toBeNull();
 });
 it('allows the required saved schedule in a sharing scope without starting its tools',async()=>{
  const schedule={id:'isolated-schedule',kind:'schedule',title:'Isolated schedule fixture',status:'Draft',version:3,data:{}};
  const fetch=install(()=>Promise.resolve(json(catalogue)),[schedule]);render(view());
  await waitFor(()=>expect(button('Fleet sharing review').disabled).toBe(false));
  fireEvent.click(button('Fleet sharing review'));
  const selection=await screen.findByRole('checkbox',{name:/Isolated schedule fixture/});fireEvent.click(selection);
  for(const [label,value] of [['What do you want to achieve?','Review the isolated sharing inputs'],['Jurisdiction','EU'],['Operation date','2026-11-05'],['Execution method','native']])fireEvent.change(screen.getByLabelText(label),{target:{value}});
  fireEvent.click(screen.getByRole('button',{name:'Create workflow'}));
  await waitFor(()=>expect(fetch.mock.calls.some(([,init])=>init?.method==='POST')).toBe(true));
  const sent=fetch.mock.calls.find(([,init])=>init?.method==='POST')!;
  expect(JSON.parse(sent[1]!.body as string).context_record_ids).toEqual(['isolated-schedule']);
  expect(fetch.mock.calls.some(([path])=>path.endsWith('/advance'))).toBe(false);
 });
 it.each(['role','organisation','token'])('retires an unsent planner when its %s changes',async scope=>{
  const next=deferred<Response>();let calls=0;install(()=>++calls===1?Promise.resolve(json(catalogue)):next.promise);
  const mounted=render(view());await waitFor(()=>expect(button('Maintenance planning').disabled).toBe(false));
  fireEvent.click(button('Maintenance planning'));fireEvent.change(screen.getByLabelText('What do you want to achieve?'),{target:{value:'Private draft from the prior context'}});
  const nextActor=scope==='role'?{...actor,role:'reviewer'}:scope==='organisation'?{...actor,organisation_id:'isolated-other'}:actor;
  mounted.rerender(view(nextActor,scope==='token'?'isolated-other-token':'isolated-token'));
  expect(screen.queryByLabelText('What do you want to achieve?')).toBeNull();expect(button('Maintenance planning').disabled).toBe(true);
  await act(async()=>next.resolve(json(catalogue)));await waitFor(()=>expect(button('Maintenance planning').disabled).toBe(false));
  expect(screen.queryByText('Private draft from the prior context')).toBeNull();
 });
 it('restores the unsent same-actor draft after a scoped permission retry',async()=>{
  let attempts=0;const fetch=install(()=>Promise.resolve(++attempts===2?json({detail:'Permission lookup unavailable'},503):json(catalogue)));
  const mounted=render(view());await waitFor(()=>expect(button('Maintenance planning').disabled).toBe(false));
  fireEvent.click(button('Maintenance planning'));fireEvent.change(screen.getByLabelText('What do you want to achieve?'),{target:{value:'Keep this actual unsent request text'}});
  mounted.rerender(<AgentWorkspace token="isolated-token" user={actor} revision={1} changed={()=>undefined}/>);
  await screen.findByRole('button',{name:'Retry workflow permissions'});expect(screen.queryByLabelText('What do you want to achieve?')).toBeNull();
  const before=fetch.mock.calls.length;fireEvent.click(screen.getByRole('button',{name:'Retry workflow permissions'}));
  const draft=await screen.findByLabelText('What do you want to achieve?') as HTMLTextAreaElement;
  expect(draft.value).toBe('Keep this actual unsent request text');
  expect(fetch.mock.calls.slice(before).map(([path])=>path)).toEqual(['/api/v1/agent-capabilities']);
  expect(fetch.mock.calls.some(([,init])=>init?.method==='POST')).toBe(false);
 });
 it('keeps schedule selection out of the unrelated maintenance scope',async()=>{
  install(()=>Promise.resolve(json(catalogue)),[{id:'isolated-schedule',kind:'schedule',title:'Isolated schedule fixture',status:'Draft',version:3,data:{}}]);
  render(view());await waitFor(()=>expect(button('Maintenance planning').disabled).toBe(false));fireEvent.click(button('Maintenance planning'));
  expect(screen.queryByRole('checkbox',{name:/Isolated schedule fixture/})).toBeNull();
 });
});
