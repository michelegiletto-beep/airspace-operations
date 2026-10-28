/** Pure presentation math. No market, account or execution dependencies. */
export const HEALTH_STATES = Object.freeze(['alive','scanning','paused','disconnected','stale','unknown','error','reconciling']);
export const MOTION_MODES = Object.freeze(['full','reduced','off']);
const clamp = (n, lo, hi) => Math.max(lo, Math.min(hi, n));
export function normalizeSeed(value) {
  if (Number.isFinite(value)) return Math.abs(value) % 65536;
  let seed = 2166136261;
  for (const c of String(value ?? '')) seed = Math.imul(seed ^ c.codePointAt(0), 16777619);
  return (seed >>> 0) % 65536;
}
export function effectiveMotion(requested='full', osReduced=false, autoReduce=true) {
  const mode = MOTION_MODES.includes(requested) ? requested : 'full';
  return autoReduce && osReduced && mode === 'full' ? 'reduced' : mode;
}
export function chooseVisualState(health, event, interaction='alive') {
  return ['paused','disconnected','stale','unknown','error','reconciling'].includes(health) ? health : event || interaction;
}
export function motionValues({seed=1,period=8,motion='full',health='unknown',event=null,pointer=[0,0],dragging=false}, now) {
  const low = ['paused','disconnected','stale','unknown','error','reconciling'].includes(health);
  const moving = motion === 'off' ? 0 : motion === 'reduced' ? .3 : 1;
  const elapsed = event ? (now-event.started)/Math.max(250,event.durationMs) : 2;
  const strength = !low && elapsed>=0 && elapsed<1 ? Math.sin(Math.PI*elapsed) * moving : 0;
  const kinds = {gather:1,send:1,hold:1,release:2,split:2,shield:3,beacon:3,ack:2,recover:3,recoil:4,uncertain:4,quiet:4,question:4,settle:4,soft:2};
  return {seed:normalizeSeed(seed)/137,period:clamp(period,6,12),activity:low?.10:health==='scanning'?.75:.5,
    time: moving ? now/1000 : 0,moving,strength,kind:kinds[event?.motion]??2,
    pointer: moving && !dragging ? pointer.map(x=>clamp(x,-1,1)) : [0,0],dragging:dragging?1:0};
}
/** Same non-rigid field used by the fallback. Exported to verify local deformation independently. */
export function deformPoint(x,y,v) {
  const t=v.time,s=v.seed,m=v.moving;
  const breath=1+.012*Math.sin(t*Math.PI*2/v.period+s)*m;
  const dx=(Math.sin(y*3.8+t*.59+s)*.022+Math.sin(x*3+y*1.8-t*.34)*.010)*m*(.45+.55*v.activity);
  const dy=(Math.sin(x*3.4-t*.47+s)*.023+Math.cos(y*3.3+t*.31)*.007)*m*(.45+.55*v.activity);
  return [(x*breath+dx+v.pointer[0]*.022*(1-.32*Math.hypot(x,y)))*.94,
    (y*breath+dy+v.pointer[1]*.022*(1-.32*Math.hypot(x,y)))*.94];
}
