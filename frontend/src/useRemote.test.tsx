import {act,cleanup,renderHook,waitFor} from '@testing-library/react';
import {afterEach,describe,expect,it,vi} from 'vitest';
import {useRemote} from './components';

type Value = {value:string};
type Scope = {path:string;token:string;revision:number;contextKey:string};
const initial:Scope = {path:'/isolated-first',token:'isolated-token-a',revision:0,contextKey:'isolated-org-a/actor-a'};
const scopes:Array<[string,Partial<Scope>]> = [
  ['path',{path:'/isolated-second'}], ['token',{token:'isolated-token-b'}],
  ['revision',{revision:1}], ['actor and tenant context',{contextKey:'isolated-org-b/actor-b'}],
];
function response(value:unknown,status=200) { return new Response(JSON.stringify(value),{status}); }
function deferred<T>() {
  let resolve!:(value:T)=>void;
  let reject!:(error:unknown)=>void;
  const promise=new Promise<T>((accept,decline)=>{resolve=accept;reject=decline;});
  return {promise,resolve,reject};
}
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});

describe('request-scoped remote reads',()=>{
  it('retries one failed GET and clears failed or prior freshness until success',async()=>{
    const recovered=deferred<Response>();
    const fetch=vi.fn().mockResolvedValueOnce(response({detail:'Isolated saved-list failure'},503)).mockImplementationOnce(()=>recovered.promise);
    vi.stubGlobal('fetch',fetch);
    const {result}=renderHook(()=>useRemote<{items:unknown[]}>('/companion/tasks','isolated-token',0,'isolated-actor'));
    await waitFor(()=>expect(result.current.error).toBe('Isolated saved-list failure'));
    expect(result.current.data).toBeNull(); expect(result.current.checkedAt).toBe(''); expect(result.current.loading).toBe(false);
    const reload=result.current.reload;
    act(()=>reload());
    expect(result.current).toMatchObject({data:null,error:'',checkedAt:'',loading:true});
    await act(async()=>recovered.resolve(response({items:[]})));
    await waitFor(()=>expect(result.current.data).toEqual({items:[]}));
    expect(result.current.loading).toBe(false); expect(result.current.error).toBe(''); expect(result.current.checkedAt).not.toBe('');
    expect(result.current.reload).toBe(reload); expect(fetch).toHaveBeenCalledTimes(2);
    for(const [url,options] of fetch.mock.calls) {
      expect(url).toBe('/api/v1/companion/tasks');
      expect(options.method??'GET').toBe('GET'); expect(options.body).toBeUndefined();
      expect(options.headers.Authorization).toBe('Bearer isolated-token'); expect(options.cache).toBe('no-store');
    }
  });

  it.each(scopes)('masks successful data and fetch time during the first changed %s render',async(_name,change)=>{
    const pending=deferred<Response>();
    const fetch=vi.fn().mockResolvedValueOnce(response({value:'Isolated prior private value'})).mockImplementationOnce(()=>pending.promise);
    vi.stubGlobal('fetch',fetch);
    const frames:Array<{scope:Scope;data:Value|null;error:string;checkedAt:string;loading:boolean}>=[];
    const {result,rerender}=renderHook((scope:Scope)=>{
      const view=useRemote<Value>(scope.path,scope.token,scope.revision,scope.contextKey);
      frames.push({scope,...view}); return view;
    },{initialProps:initial});
    await waitFor(()=>expect(result.current.data?.value).toBe('Isolated prior private value'));
    const offset=frames.length;
    const next={...initial,...change}; rerender(next);
    expect(frames[offset]).toMatchObject({scope:next,data:null,error:'',checkedAt:'',loading:true});
    expect(result.current).toMatchObject({data:null,error:'',checkedAt:'',loading:true});
  });

  it.each(scopes)('masks errors before the effect for a changed %s scope starts',async(_name,change)=>{
    const pending=deferred<Response>();
    vi.stubGlobal('fetch',vi.fn().mockResolvedValueOnce(response({detail:'Isolated prior-scope error'},403)).mockImplementationOnce(()=>pending.promise));
    const frames:Array<{error:string;data:Value|null;checkedAt:string;loading:boolean}>=[];
    const {result,rerender}=renderHook((scope:Scope)=>{
      const view=useRemote<Value>(scope.path,scope.token,scope.revision,scope.contextKey); frames.push(view); return view;
    },{initialProps:initial});
    await waitFor(()=>expect(result.current.error).toBe('Isolated prior-scope error'));
    const offset=frames.length; rerender({...initial,...change});
    expect(frames[offset]).toMatchObject({data:null,error:'',checkedAt:'',loading:true});
  });

  for(const outcome of ['resolve','reject'] as const) {
    it.each(scopes)(`ignores a late ${outcome} after a newer %s read completes, even when transport ignores abort`,async(_name,change)=>{
      const old=deferred<Response>(),latest=deferred<Response>();
      const fetch=vi.fn().mockImplementationOnce(()=>old.promise).mockImplementationOnce(()=>latest.promise);
      vi.stubGlobal('fetch',fetch);
      const {result,rerender}=renderHook((scope:Scope)=>useRemote<Value>(scope.path,scope.token,scope.revision,scope.contextKey),{initialProps:initial});
      rerender({...initial,...change});
      expect((fetch.mock.calls[0][1].signal as AbortSignal).aborted).toBe(true);
      await act(async()=>latest.resolve(response({value:'Isolated current value'})));
      await waitFor(()=>expect(result.current.data?.value).toBe('Isolated current value'));
      const checkedAt=result.current.checkedAt;
      await act(async()=>{if(outcome==='resolve')old.resolve(response({value:'Isolated obsolete value'}));else old.reject(new Error('Isolated late non-abort error'));});
      expect(result.current).toMatchObject({data:{value:'Isolated current value'},error:'',loading:false,checkedAt});
      expect(fetch).toHaveBeenCalledTimes(2);
    });
  }

  it('does not accept an old JSON body that completes after its fetch was aborted',async()=>{
    const body=deferred<Value>(); const json=vi.fn(()=>body.promise);
    const fetch=vi.fn().mockResolvedValueOnce({ok:true,json}).mockResolvedValueOnce(response({value:'Isolated latest parsed value'}));
    vi.stubGlobal('fetch',fetch);
    const {result,rerender}=renderHook((scope:Scope)=>useRemote<Value>(scope.path,scope.token,scope.revision,scope.contextKey),{initialProps:initial});
    await waitFor(()=>expect(json).toHaveBeenCalledOnce());
    rerender({...initial,token:'isolated-current-token'});
    await waitFor(()=>expect(result.current.data?.value).toBe('Isolated latest parsed value'));
    const checkedAt=result.current.checkedAt;
    await act(async()=>body.resolve({value:'Isolated obsolete parsed value'}));
    expect(result.current).toMatchObject({data:{value:'Isolated latest parsed value'},error:'',loading:false,checkedAt});
  });

  it('isolates reload to one hook without refetching a conversation or sending mutations',async()=>{
    const fetch=vi.fn(async(url:string)=>response({value:url})); vi.stubGlobal('fetch',fetch);
    const {result}=renderHook(()=>({tasks:useRemote<Value>('/companion/tasks','isolated-token'),conversations:useRemote<Value>('/companion/conversations','isolated-token')}));
    await waitFor(()=>expect(result.current.tasks.loading||result.current.conversations.loading).toBe(false));
    act(()=>result.current.tasks.reload());
    await waitFor(()=>expect(fetch).toHaveBeenCalledTimes(3));
    expect(fetch.mock.calls.filter(([url])=>url==='/api/v1/companion/tasks')).toHaveLength(2);
    expect(fetch.mock.calls.filter(([url])=>url==='/api/v1/companion/conversations')).toHaveLength(1);
    for(const call of fetch.mock.calls) {
      const options=(call as unknown as [string,RequestInit])[1];
      expect(options.method??'GET').toBe('GET'); expect(options.body).toBeUndefined();
    }
  });

  it('uses the current token and path when an older reload callback is invoked',async()=>{
    const fetch=vi.fn(async()=>response({value:'Isolated response'})); vi.stubGlobal('fetch',fetch);
    const {result,rerender}=renderHook((scope:Scope)=>useRemote<Value>(scope.path,scope.token,scope.revision,scope.contextKey),{initialProps:initial});
    await waitFor(()=>expect(result.current.loading).toBe(false));
    const oldReload=result.current.reload;
    rerender({...initial,path:'/isolated-current',token:'isolated-new-token'});
    await waitFor(()=>expect(result.current.loading).toBe(false));
    act(()=>oldReload());
    await waitFor(()=>expect(fetch).toHaveBeenCalledTimes(3));
    const call=fetch.mock.calls[2] as unknown as [string,RequestInit];
    expect(call[0]).toBe('/api/v1/isolated-current');
    expect((call[1].headers as Record<string,string>).Authorization).toBe('Bearer isolated-new-token');
  });

  it('aborts its outstanding read when unmounted',async()=>{
    const pending=deferred<Response>(); const fetch=vi.fn(()=>pending.promise); vi.stubGlobal('fetch',fetch);
    const {unmount}=renderHook(()=>useRemote<Value>('/isolated-read','isolated-token'));
    const signal=(fetch.mock.calls[0] as unknown as [string,RequestInit])[1].signal as AbortSignal;
    expect(signal.aborted).toBe(false); unmount(); expect(signal.aborted).toBe(true);
    await act(async()=>pending.resolve(response({value:'Isolated late unmounted value'})));
    expect(fetch).toHaveBeenCalledOnce();
  });
});
