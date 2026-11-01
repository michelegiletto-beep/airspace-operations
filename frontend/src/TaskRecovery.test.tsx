import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {CompanionDock} from './CompanionDock';
import type {User} from './api';
vi.mock('./companionRuntime',()=>({loadCompanionRuntime:vi.fn().mockRejectedValue(new Error('Isolated renderer outage'))}));
const user:User={id:'isolated-task-owner',email:'owner@test.invalid',role:'regulatory',organisation_id:'isolated-task-tenant'};
const task={id:'isolated-task',kind:'companion_task',title:'Isolated saved task',status:'Open',version:3,created_by:user.id,created_at:'2026-01-01T00:00:00Z',updated_at:'2026-01-01T00:00:00Z',data:{owner_actor_id:user.id,conversation_id:'isolated-conversation',description:'A software-test task only.'}};
const json=(value:unknown,status=200)=>new Response(JSON.stringify(value),{status});
function install(reads:Array<()=>Response|Promise<Response>>){
 const fetcher=vi.fn(async(url:string,_init:RequestInit={})=>{
  if(url==='/api/v1/companion/tasks')return (reads.shift()??(()=>json({items:[task]})))();
  if(url==='/api/v1/companion/catalog')return json({workspaces:[],action_kinds:[],model_status:{state:'Not Installed',message:'Isolated test has no model.'}});
  return json({items:[]});
 });vi.stubGlobal('fetch',fetcher);return fetcher;
}
function mount(){const changed=vi.fn();render(<CompanionDock token="isolated-task-token" user={user} workspace="operations" workspaceLabel="Operations" revision={0} changed={changed} open onOpenChange={()=>undefined} openWorkflow={()=>undefined}/>);return changed;}
beforeEach(()=>{sessionStorage.clear();localStorage.clear();});
afterEach(()=>{cleanup();vi.unstubAllGlobals();sessionStorage.clear();localStorage.clear();});
describe('saved-task read recovery',()=>{
 it('retries only the failed read, keeps the conversation draft and does not create or confirm work',async()=>{
  let resolve!:(r:Response)=>void;const pending=new Promise<Response>(r=>{resolve=r;});
  const fetcher=install([()=>json({detail:'Isolated temporary read failure'},503),()=>pending]);
  const changed=mount();fireEvent.change(screen.getByLabelText('Your request'),{target:{value:'Keep this unsent draft'}});
  fireEvent.click(screen.getByRole('tab',{name:/Tasks/}));
  await screen.findByRole('heading',{name:'Saved tasks unavailable'});
  expect(screen.queryByRole('heading',{name:'No saved tasks'})).toBeNull();
  const before=fetcher.mock.calls.filter(([p])=>p!=='/api/v1/companion/tasks').map(([p])=>p);
  const retry=screen.getByRole('button',{name:'Retry saved tasks'});
  fireEvent.click(retry);
  await waitFor(()=>expect(fetcher.mock.calls.filter(([p])=>p==='/api/v1/companion/tasks')).toHaveLength(2));
  expect((screen.getByRole('button',{name:'Loading saved tasks…'}) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.queryByRole('heading',{name:'No saved tasks'})).toBeNull();
  resolve(json({items:[task]}));await screen.findByRole('heading',{name:task.title});
  expect(screen.getByRole('button',{name:'Reload saved tasks'})).toBeTruthy();
  expect((screen.getByLabelText('Task state for '+task.title) as HTMLSelectElement).value).toBe('Open');
  expect(fetcher.mock.calls.filter(([p])=>p!=='/api/v1/companion/tasks').map(([p])=>p)).toEqual(before);
  expect(changed).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('tab',{name:'Conversation'}));
  expect((screen.getByLabelText('Your request') as HTMLTextAreaElement).value).toBe('Keep this unsent draft');
  expect(fetcher.mock.calls.every(([,init])=>!init?.method || init.method==='GET')).toBe(true);
 });
 it('shows empty only after a successful current empty list, including repeated failures',async()=>{
  install([()=>json({detail:'First isolated failure'},503),()=>json({detail:'Second isolated failure'},503),()=>json({items:[]})]);mount();
  fireEvent.click(screen.getByRole('tab',{name:/Tasks/}));await screen.findByText('First isolated failure');
  fireEvent.click(screen.getByRole('button',{name:'Retry saved tasks'}));await screen.findByText('Second isolated failure');
  expect(screen.queryByRole('heading',{name:'No saved tasks'})).toBeNull();
  fireEvent.click(screen.getByRole('button',{name:'Retry saved tasks'}));await screen.findByRole('heading',{name:'No saved tasks'});
  expect(screen.queryByRole('heading',{name:'Saved tasks unavailable'})).toBeNull();
 });
 it.each([null,{items:null},{items:[null]},{items:[{...task,created_by:'other-actor',data:{...task.data,owner_actor_id:'other-actor'},title:'Other actor private task'}]}])('does not turn a malformed or wrong-owner response into an empty or disclosed list: %j',async value=>{
  install([()=>json(value)]);mount();fireEvent.click(screen.getByRole('tab',{name:/Tasks/}));
  await screen.findByRole('heading',{name:'Saved tasks unavailable'});
  expect(screen.queryByRole('heading',{name:'No saved tasks'})).toBeNull();
  expect(screen.queryByText('Other actor private task')).toBeNull();
  expect(screen.getByRole('button',{name:'Retry saved tasks'})).toBeTruthy();
 });
 it('can refresh a successful list without changing any saved task',async()=>{
  const fetcher=install([()=>json({items:[task]}),()=>json({items:[{...task,status:'Completed',version:4}]})]);const changed=mount();
  fireEvent.click(screen.getByRole('tab',{name:/Tasks/}));await screen.findByRole('heading',{name:task.title});
  fireEvent.click(screen.getByRole('button',{name:'Reload saved tasks'}));
  await waitFor(()=>expect((screen.getByLabelText('Task state for '+task.title) as HTMLSelectElement).value).toBe('Completed'));
  expect(fetcher.mock.calls.filter(([p])=>p==='/api/v1/companion/tasks')).toHaveLength(2);expect(changed).not.toHaveBeenCalled();
 });
});
