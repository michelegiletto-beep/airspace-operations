import { MASCOTS } from './catalog.mjs';
import { HEALTH_STATES, effectiveMotion, motionValues } from './motion-core.mjs';

// One shared GPU context and scheduler per document, including hub, dialogs and docks.
// The target canvas remains in normal DOM layout; no global overlay can cover a chart.
const documents = new WeakMap();
const instances = new WeakMap();
const VERT = `
precision mediump float;
attribute vec2 aPosition; attribute vec2 aUv;
uniform float uTime,uSeed,uActivity,uEvent,uKind,uMoving,uPeriod,uDragging;
uniform vec2 uPointer; varying vec2 vUv;
void main(){
 vec2 p=aPosition; float t=uTime,s=uSeed;
 float breath=1.0+.012*sin(t*6.283185/uPeriod+s)*uMoving;
 float dx=sin(p.y*3.8+t*.59+s)*.022+sin(p.x*3.0+p.y*1.8-t*.34)*.010;
 float dy=sin(p.x*3.4-t*.47+s)*.023+cos(p.y*3.3+t*.31)*.007;
 p+=vec2(dx,dy)*uMoving*(.45+.55*uActivity);
 float pull=uKind<1.5?-.028*uEvent:uKind<3.5?.035*uEvent:-.015*uEvent;
 p*=breath+pull;
 float angle=sin(t*.17+s)*.022*uMoving*(1.0-uDragging)+uPointer.x*.022;
 p=mat2(cos(angle),-sin(angle),sin(angle),cos(angle))*p;
 p+=uPointer*.022*(1.0-.32*length(p));
 gl_Position=vec4(p*.94,0.0,1.0);vUv=aUv;
}`;
const FRAG = `
precision mediump float; varying vec2 vUv; uniform sampler2D uImage;
uniform float uTime,uSeed,uActivity,uEvent,uKind,uMoving;uniform vec2 uPointer;
void main(){
 vec2 uv=vUv,c=uv-.5;float r=length(c),inner=max(0.0,1.0-r*1.8);
 uv+=vec2(sin(uv.y*9.0+uTime*.37+uSeed),cos(uv.x*8.0-uTime*.29))*.003*inner*uMoving;
 vec4 tex=texture2D(uImage,uv);
 float filament=.5+.5*sin(uv.x*15.0+uv.y*11.0-uTime*.72+uSeed);
 float wave=exp(-pow((r-.31-.12*sin(uTime*1.5))*17.0,2.0))*uEvent;
 float sheen=exp(-pow((uv.x+uv.y*.40-.62-uPointer.x*.10-sin(uTime*.21)*.08)*10.0,2.0));
 float gain=.98+.045*filament*inner*uActivity*uMoving;
 vec3 color=tex.rgb*gain+vec3(.82,.91,1.0)*(.012*sheen*uMoving+.055*wave)*tex.a;
 gl_FragColor=vec4(min(color,vec3(tex.a)),tex.a);
}`;
function compile(gl,type,source){const shader=gl.createShader(type);gl.shaderSource(shader,source);gl.compileShader(shader);if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS)){const error=gl.getShaderInfoLog(shader);gl.deleteShader(shader);throw new Error(error||'Shader unavailable');}return shader;}

class SharedScene {
 constructor(doc){
  this.doc=doc;this.win=doc.defaultView;this.slots=new Set();this.images=new Map();this.textures=new Map();this.pending=new Map();this.frameTimes=[];this.raf=0;this.frames=0;this.lastFrame=0;this.gl=null;this.contextLost=false;this.dead=false;
  this.surface=doc.createElement('canvas');this.surface.width=384;this.surface.height=384;
  this.os=this.win.matchMedia?.('(prefers-reduced-motion: reduce)');
  this.onVisibility=()=>{if(doc.hidden){this.win.cancelAnimationFrame(this.raf);this.raf=0;}else this.invalidate(true);};
  this.onMotion=()=>this.invalidate(true);
  this.onLost=e=>{e.preventDefault();this.contextLost=true;this.engine='canvas2d-deformation';this.invalidate(true);};
  this.onRestore=()=>{this.contextLost=false;try{this.initGL();}catch(e){this.error=String(e.message);this.gl=null;}this.invalidate(true);};
  this.surface.addEventListener('webglcontextlost',this.onLost);this.surface.addEventListener('webglcontextrestored',this.onRestore);
  doc.addEventListener('visibilitychange',this.onVisibility);this.os?.addEventListener?.('change',this.onMotion);
  try{this.gl=this.surface.getContext('webgl',{alpha:true,premultipliedAlpha:true,antialias:false,depth:false,stencil:false,preserveDrawingBuffer:false});if(this.gl)this.initGL();}catch(e){this.error=String(e.message);this.gl=null;}
  this.engine=this.gl?'webgl-mesh-2.5d':'canvas2d-deformation';
 }
 initGL(){
  const gl=this.gl;if(!gl)return;
  this.releaseGPU();
  const vs=compile(gl,gl.VERTEX_SHADER,VERT),fs=compile(gl,gl.FRAGMENT_SHADER,FRAG),p=gl.createProgram();gl.attachShader(p,vs);gl.attachShader(p,fs);gl.linkProgram(p);gl.deleteShader(vs);gl.deleteShader(fs);
  if(!gl.getProgramParameter(p,gl.LINK_STATUS)){const reason=gl.getProgramInfoLog(p);gl.deleteProgram(p);throw new Error(reason||'Mascot GPU program unavailable');}
  this.program=p;gl.useProgram(p);const n=28,vertices=[],indices=[];
  for(let y=0;y<=n;y++)for(let x=0;x<=n;x++)vertices.push(x/n*2-1,y/n*2-1,x/n,1-y/n);
  for(let y=0;y<n;y++)for(let x=0;x<n;x++){const a=y*(n+1)+x;indices.push(a,a+1,a+n+1,a+1,a+n+2,a+n+1);}
  this.vb=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,this.vb);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(vertices),gl.STATIC_DRAW);
  this.ib=gl.createBuffer();gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,this.ib);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,new Uint16Array(indices),gl.STATIC_DRAW);this.indexCount=indices.length;
  for(const [name,offset]of[['aPosition',0],['aUv',8]]){const a=gl.getAttribLocation(p,name);gl.enableVertexAttribArray(a);gl.vertexAttribPointer(a,2,gl.FLOAT,false,16,offset);}
  this.uniforms=Object.fromEntries(['uImage','uTime','uSeed','uActivity','uEvent','uKind','uMoving','uPointer','uPeriod','uDragging'].map(k=>[k,gl.getUniformLocation(p,k)]));
  gl.uniform1i(this.uniforms.uImage,0);gl.disable(gl.DEPTH_TEST);gl.enable(gl.BLEND);gl.blendFunc(gl.ONE,gl.ONE_MINUS_SRC_ALPHA);
  for(const [id,image]of this.images)this.upload(id,image);this.engine='webgl-mesh-2.5d';
 }
 upload(id,image){const gl=this.gl;if(!gl||this.contextLost||this.dead)return;const old=this.textures.get(id);if(old)gl.deleteTexture(old);const tex=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,tex);gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL,true);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,image);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);this.textures.set(id,tex);}
 load(id){
  if(this.images.has(id))return Promise.resolve(this.images.get(id));if(this.pending.has(id))return this.pending.get(id);
  const asset=MASCOTS.find(x=>x.id===id);if(!asset)return Promise.reject(new Error('Unknown mascot identity'));
  const promise=new Promise((resolve,reject)=>{const image=new this.win.Image();image.onload=()=>{this.pending.delete(id);if(!this.dead){this.images.set(id,image);this.upload(id,image);this.invalidate(true);}resolve(image);};image.onerror=()=>{this.pending.delete(id);reject(new Error(`Mascot asset unavailable: ${id}`));};image.src=asset.source;});this.pending.set(id,promise);return promise;
 }
 invalidate(force=false){if(force)for(const slot of this.slots)slot.dirty=true;if(this.dead||this.doc.hidden||this.raf)return;this.raf=this.win.requestAnimationFrame(now=>this.frame(now));}
 frame(now){
  this.raf=0;if(this.dead||this.doc.hidden)return;const started=this.win.performance.now();let animate=false,draws=0;
  for(const slot of this.slots){
   if(slot.dead||!slot.visible||!slot.intersecting||!slot.canvas.isConnected)continue;
   const mode=effectiveMotion(slot.motion,this.os?.matches,slot.autoReduceMotion);const interval=mode==='reduced'?1000/15:1000/30;
   if(mode!=='off')animate=true;if(!slot.dirty&&(mode==='off'||now-slot.lastFrame<interval-1))continue;
   const image=this.images.get(slot.mascotId);if(!image)continue;
   const rect=slot.canvas.getBoundingClientRect();if(rect.width<=0||rect.height<=0)continue;
   const maxDpr=mode==='reduced'?1.25:1.75,dpr=Math.min(this.win.devicePixelRatio||1,maxDpr);const w=Math.min(768,Math.max(1,Math.round(rect.width*dpr))),h=Math.min(768,Math.max(1,Math.round(rect.height*dpr)));
   if(slot.canvas.width!==w||slot.canvas.height!==h){slot.canvas.width=w;slot.canvas.height=h;}
   slot.pointer[0]+=(slot.targetPointer[0]-slot.pointer[0])*.13;slot.pointer[1]+=(slot.targetPointer[1]-slot.pointer[1])*.13;
   const asset=MASCOTS.find(x=>x.id===slot.mascotId);const v=motionValues({seed:slot.appearanceSeed??asset.seed,period:asset.idlePeriodSeconds,motion:mode,health:slot.health,event:slot.event,pointer:slot.pointer,dragging:slot.dragging},now);
   if(slot.event&&now-slot.event.started>slot.event.durationMs)slot.event=null;
   const ctx=slot.ctx;ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,w,h);const size=Math.min(w,h),left=(w-size)/2,top=(h-size)/2;
   try{if(this.gl&&!this.contextLost&&this.textures.has(slot.mascotId)){this.drawGL(slot.mascotId,v,size);ctx.drawImage(this.surface,0,0,size,size,left,top,size,size);}else this.drawFallback(ctx,image,v,left,top,size);}
   catch(e){this.error=String(e.message);this.contextLost=true;this.engine='canvas2d-deformation';this.drawFallback(ctx,image,v,left,top,size);}
   slot.canvas.dataset.mascotEngine=this.engine;slot.canvas.dataset.mascotMotion=mode;slot.lastFrame=now;slot.dirty=false;slot.frames++;draws++;
  }
  if(draws){this.frames++;this.frameTimes.push(this.win.performance.now()-started);if(this.frameTimes.length>300)this.frameTimes.shift();}if(animate)this.invalidate();
 }
 drawGL(id,v,size){
  const gl=this.gl;if(this.surface.width!==size||this.surface.height!==size){this.surface.width=size;this.surface.height=size;}
  gl.viewport(0,0,size,size);gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT);gl.useProgram(this.program);gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,this.textures.get(id));
  for(const [key,val]of[['uTime',v.time],['uSeed',v.seed],['uActivity',v.activity],['uEvent',v.strength],['uKind',v.kind],['uMoving',v.moving],['uPeriod',v.period],['uDragging',v.dragging]])gl.uniform1f(this.uniforms[key],val);
  gl.uniform2f(this.uniforms.uPointer,v.pointer[0],v.pointer[1]);gl.drawElements(gl.TRIANGLES,this.indexCount,gl.UNSIGNED_SHORT,0);
 }
 drawFallback(ctx,image,v,left,top,size){
  ctx.save();ctx.translate(left+size/2,top+size/2);const body=size*.94;
  const breath=1+.012*Math.sin(v.time*Math.PI*2/v.period+v.seed)*v.moving+v.strength*(v.kind<1.5?-.025:.03);ctx.scale(breath,breath);
  const strips=v.moving?28:1;
  for(let n=0;n<strips;n++){const sx=n*image.width/strips,sw=image.width/strips,dy=Math.sin(n*.24+v.time*.55+v.seed)*body*.01*v.moving;ctx.drawImage(image,sx,0,sw,image.height,-body/2+n*body/strips+v.pointer[0]*2,-body/2+dy-v.pointer[1]*2,body/strips+.2,body);}
  if(v.moving){ctx.globalCompositeOperation='source-atop';const p=(Math.sin(v.time*.45+v.seed)+1)/2;const glow=ctx.createRadialGradient(body*(p-.5)*.65,0,0,body*(p-.5)*.65,0,body*.35);glow.addColorStop(0,`rgba(224,237,250,${.03*v.activity+.10*v.strength})`);glow.addColorStop(1,'rgba(224,237,250,0)');ctx.fillStyle=glow;ctx.fillRect(-body/2,-body/2,body,body);}
  ctx.restore();
 }
 releaseGPU(){const gl=this.gl;if(!gl)return;for(const tex of this.textures.values())gl.deleteTexture(tex);this.textures.clear();if(this.vb)gl.deleteBuffer(this.vb);if(this.ib)gl.deleteBuffer(this.ib);if(this.program)gl.deleteProgram(this.program);}
 diagnostics(){const sorted=[...this.frameTimes].sort((a,b)=>a-b);return {engine:this.engine,frames:this.frames,instances:this.slots.size,textureCount:this.textures.size,contextLost:this.contextLost,frameP50Ms:sorted[Math.floor(sorted.length*.5)]??0,frameP95Ms:sorted[Math.floor(sorted.length*.95)]??0,error:this.error??null};}
 dispose(){this.dead=true;this.win.cancelAnimationFrame(this.raf);this.raf=0;this.doc.removeEventListener('visibilitychange',this.onVisibility);this.os?.removeEventListener?.('change',this.onMotion);this.surface.removeEventListener('webglcontextlost',this.onLost);this.surface.removeEventListener('webglcontextrestored',this.onRestore);this.releaseGPU();this.gl?.getExtension('WEBGL_lose_context')?.loseContext();this.images.clear();this.pending.clear();documents.delete(this.doc);}
}

export function mountMascot(canvas,options={}){
 if(!canvas?.ownerDocument||typeof canvas.getContext!=='function')throw new TypeError('A canvas element is required');
 instances.get(canvas)?.destroy();const doc=canvas.ownerDocument;let scene=documents.get(doc);if(!scene){scene=new SharedScene(doc);documents.set(doc,scene);}
 const ctx=canvas.getContext('2d',{alpha:true});if(!ctx)throw new Error('Canvas output is unavailable');
 const slot={canvas,ctx,mascotId:MASCOTS.some(x=>x.id===options.mascotId)?options.mascotId:'mascot-01',appearanceSeed:options.appearanceSeed,motion:options.motion??'full',autoReduceMotion:options.autoReduceMotion!==false,visible:options.visible!==false,health:HEALTH_STATES.includes(options.state)?options.state:'unknown',event:null,pointer:[0,0],targetPointer:[0,0],dragging:false,intersecting:true,dirty:true,dead:false,lastFrame:-Infinity,frames:0};
 canvas.setAttribute('role','img');canvas.setAttribute('aria-label',options.label||'Presenza animata dell’agente');canvas.dataset.mascotState=slot.health;
 const onMove=e=>{const r=canvas.getBoundingClientRect();slot.targetPointer=[(e.clientX-r.left-r.width/2)/(r.width/2),-(e.clientY-r.top-r.height/2)/(r.height/2)];scene.invalidate();};
 const onLeave=()=>{slot.targetPointer=[0,0];scene.invalidate();};const onDown=()=>{slot.dragging=true;scene.invalidate();};const onUp=()=>{if(slot.dragging){slot.dragging=false;api.trigger('ack',900,5);}};
 canvas.addEventListener('pointermove',onMove,{passive:true});canvas.addEventListener('pointerleave',onLeave,{passive:true});canvas.addEventListener('pointerdown',onDown,{passive:true});doc.defaultView.addEventListener('pointerup',onUp,{passive:true});doc.defaultView.addEventListener('pointercancel',onUp,{passive:true});
 const resize=typeof doc.defaultView.ResizeObserver==='function'?new doc.defaultView.ResizeObserver(()=>{slot.dirty=true;scene.invalidate();}):null;resize?.observe(canvas);
 const intersect=typeof doc.defaultView.IntersectionObserver==='function'?new doc.defaultView.IntersectionObserver(entries=>{slot.intersecting=entries[0]?.isIntersecting!==false;slot.dirty=true;scene.invalidate();}):null;intersect?.observe(canvas);
 scene.slots.add(slot);
 const load=()=>scene.load(slot.mascotId).catch(error=>{canvas.dataset.mascotError='asset_unavailable';options.onError?.(error);return null;});
 const api={ready:null,setState(state){if(slot.dead)return;const health=typeof state==='string'?state:state?.health;if(HEALTH_STATES.includes(health)){slot.health=health;canvas.dataset.mascotState=health;}if(state?.event)api.trigger(state.event.motion,state.event.durationMs,state.event.priority);slot.dirty=true;scene.invalidate();},
  setPreferences(values={}){if(slot.dead)return;for(const key of ['appearanceSeed','motion','autoReduceMotion','visible'])if(Object.hasOwn(values,key))slot[key]=values[key];if(MASCOTS.some(x=>x.id===values.mascotId)){slot.mascotId=values.mascotId;api.ready=load();}canvas.style.visibility=slot.visible?'':'hidden';slot.dirty=true;scene.invalidate();},
  trigger(motion='soft',durationMs=1800,priority=20){if(slot.dead)return;if(slot.event&&slot.event.priority>priority&&scene.win.performance.now()-slot.event.started<slot.event.durationMs)return;slot.event={motion,durationMs:Math.min(6000,Math.max(250,Number(durationMs)||1800)),priority:Number(priority)||0,started:scene.win.performance.now()};slot.dirty=true;scene.invalidate();},
  diagnostics(){return {...scene.diagnostics(),slotFrames:slot.frames,mascotId:slot.mascotId,health:slot.health,motion:effectiveMotion(slot.motion,scene.os?.matches,slot.autoReduceMotion),visible:slot.visible&&slot.intersecting};},
  destroy(){if(slot.dead)return;slot.dead=true;resize?.disconnect();intersect?.disconnect();canvas.removeEventListener('pointermove',onMove);canvas.removeEventListener('pointerleave',onLeave);canvas.removeEventListener('pointerdown',onDown);doc.defaultView.removeEventListener('pointerup',onUp);doc.defaultView.removeEventListener('pointercancel',onUp);scene.slots.delete(slot);ctx.clearRect(0,0,canvas.width,canvas.height);instances.delete(canvas);if(!scene.slots.size)scene.dispose();}
 };instances.set(canvas,api);api.ready=load();api.setPreferences({visible:slot.visible});return api;
}
export function rendererDiagnostics(doc=globalThis.document){return documents.get(doc)?.diagnostics()??{engine:'inactive',instances:0,textureCount:0,frames:0};}
