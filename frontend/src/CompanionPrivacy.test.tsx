import {createElement,Suspense,startTransition,useState} from 'react';
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {CompanionDock} from './CompanionDock';
import type {User} from './api';

vi.mock('./companionRuntime',()=>({loadCompanionRuntime:vi.fn().mockRejectedValue(new Error('Isolated renderer outage'))}));
const a:User={id:'isolated-actor-a',email:'a@test.invalid',organisation_id:'isolated-org-a',role:'regulatory'};
const b:User={id:'isolated-actor-b',email:'b@test.invalid',organisation_id:'isolated-org-b',role:'regulatory'};
const prefix=(user:User)=>`sl-airspace-companion-draft:${user.organisation_id}:${user.id}`;
const conversation={id:'isolated-conversation-a',kind:'companion_conversation',title:'Actor A conversation',status:'Ready',version:1,created_by:a.id,created_at:'2026-01-01T00:00:00Z',updated_at:'2026-01-01T00:00:00Z',data:{owner_actor_id:a.id,workspace:'operations',context_record_versions:{},active_message_id:null,next_turn:1}};
const baseProps=(user:User,token='isolated-token-'+user.id)=>({token,user,workspace:'operations',workspaceLabel:'Operations',revision:0,changed:vi.fn(),open:true,onOpenChange:vi.fn(),openWorkflow:vi.fn()});
const json=(value:unknown,status=200)=>new Response(JSON.stringify(value),{status});

function install(){
 const fetcher=vi.fn(async(url:string,init:RequestInit={})=>{
  const isA=(init.headers as Record<string,string>)?.Authorization==='Bearer isolated-token-'+a.id;
  if(url.endsWith('/catalog'))return json({workspaces:[],action_kinds:[],model_status:{state:'Not Installed',message:'No model in isolated test.'}});
  if(url.endsWith('/companion/conversations/isolated-conversation-a'))return isA?json({conversation,messages:[{...conversation,id:'isolated-reply-a',kind:'companion_message',data:{role:'assistant',text:'Private actor A saved reply',reply_kind:'fallback'}}],action_previews:[],tasks:[],active_job:null,model_status:{state:'Not Installed'}}):json({detail:'Not found for current actor'},404);
  return json({items:[]});
 });vi.stubGlobal('fetch',fetcher);return fetcher;
}
beforeEach(()=>{sessionStorage.clear();localStorage.clear();});
afterEach(()=>{cleanup();sessionStorage.clear();localStorage.clear();vi.unstubAllGlobals();});

describe('companion identity boundary',()=>{
 it('keeps committed actor A usable when a pending actor B render is abandoned in Suspense',async()=>{
  install();const forever=new Promise<void>(()=>{});let change!:(user:User)=>void;
  function Pending({user}:{user:User}){if(user.id===b.id)throw forever;return null;}
  function Pane(){const [user,setUser]=useState(a);change=setUser;return createElement(Suspense,{fallback:createElement('p',null,'Loading actor')},createElement(CompanionDock,baseProps(user)),createElement(Pending,{user}));}
  render(createElement(Pane));
  fireEvent.change(screen.getByLabelText('Your request'),{target:{value:'Committed actor A draft'}});
  await act(async()=>{startTransition(()=>change(b));});
  fireEvent.change(screen.getByLabelText('Your request'),{target:{value:'Actor A can still edit'}});
  expect((screen.getByLabelText('Your request') as HTMLTextAreaElement).value).toBe('Actor A can still edit');
  expect(JSON.parse(sessionStorage.getItem(prefix(a)+':message')!)).toBe('Actor A can still edit');
  expect(sessionStorage.getItem(prefix(b)+':message')).toBeNull();
 });
 it('clears loaded replies and restores only the new actor draft on an actor and tenant transition',async()=>{
  sessionStorage.setItem(prefix(a)+':conversation-id',JSON.stringify(conversation.id));
  sessionStorage.setItem(prefix(b)+':message',JSON.stringify('Actor B unsent draft'));
  const fetcher=install();const view=render(createElement(CompanionDock,baseProps(a)));
  await screen.findByText('Private actor A saved reply');
  fireEvent.change(screen.getByLabelText('Your request'),{target:{value:'Private actor A unsent draft'}});
  view.rerender(createElement(CompanionDock,baseProps(b)));
  expect(screen.queryByText('Private actor A saved reply')).toBeNull();
  expect((screen.getByLabelText('Your request') as HTMLTextAreaElement).value).toBe('Actor B unsent draft');
  expect(JSON.parse(sessionStorage.getItem(prefix(a)+':message')!)).toBe('Private actor A unsent draft');
  expect(JSON.parse(sessionStorage.getItem(prefix(b)+':message')!)).toBe('Actor B unsent draft');
  expect(fetcher.mock.calls.every(([,init])=>!init?.method||init?.method==='GET')).toBe(true);
 });

 it.each(['token','role'] as const)('resets transient view state on a %s change while preserving the same actor draft',async field=>{
  install();const props=baseProps(a);const view=render(createElement(CompanionDock,props));
  fireEvent.change(screen.getByLabelText('Your request'),{target:{value:'Retained same-actor draft'}});
  fireEvent.click(screen.getByRole('tab',{name:/Tasks/}));
  await screen.findByRole('heading',{name:'No saved tasks'});
  const next=field==='token'?{...props,token:'isolated-rotated-token'}:{...props,user:{...a,role:'reviewer'}};
  view.rerender(createElement(CompanionDock,next));
  expect(screen.getByRole('tab',{name:'Conversation'}).getAttribute('aria-selected')).toBe('true');
  expect((screen.getByLabelText('Your request') as HTMLTextAreaElement).value).toBe('Retained same-actor draft');
 });

 it('ignores an already-authorized old response after identity changes without sending work for the new actor',async()=>{
  let resolve!:(response:Response)=>void;
  const pending=new Promise<Response>(done=>{resolve=done;});
  const fetcher=install();fetcher.mockImplementation(async(url:string,init:RequestInit={})=>{
   if(url==='/api/v1/companion/conversations'&&init?.method==='POST')return pending;
   if(url.endsWith('/catalog'))return json({workspaces:[],action_kinds:[],model_status:{state:'Not Installed'}});
   if(url.endsWith('/messages'))return json({detail:'Isolated old actor request rejected'},409);
   return json({items:[]});
  });
  const view=render(createElement(CompanionDock,baseProps(a)));
  fireEvent.change(screen.getByLabelText('Your request'),{target:{value:'An isolated old actor request'}});
  fireEvent.click(screen.getByRole('button',{name:'Send'}));
  await waitFor(()=>expect(fetcher.mock.calls.some(([,init])=>init?.method==='POST')).toBe(true));
  view.rerender(createElement(CompanionDock,baseProps(b)));
  await act(async()=>{resolve(json(conversation,201));await pending;});
  expect((screen.getByLabelText('Your request') as HTMLTextAreaElement).value).toBe('');
  expect(sessionStorage.getItem(prefix(b)+':conversation-id')).toBe('""');
  expect(fetcher.mock.calls.filter(([,init])=>init?.method==='POST')).toHaveLength(1);
  expect(fetcher.mock.calls.some(([url])=>url.endsWith('/messages'))).toBe(false);
  expect(fetcher.mock.calls.filter(([,init])=>init?.method==='POST').every(([,init])=>(init?.headers as Record<string,string>).Authorization==='Bearer isolated-token-'+a.id)).toBe(true);
 });

 it('is empty when unmounted before another actor mounts, matching the normal App sign-out boundary',()=>{
  install();const view=render(createElement(CompanionDock,baseProps(a)));
  fireEvent.change(screen.getByLabelText('Your request'),{target:{value:'Actor A unsent draft'}});
  view.unmount();render(createElement(CompanionDock,baseProps(b)));
  expect((screen.getByLabelText('Your request') as HTMLTextAreaElement).value).toBe('');
 });
});
