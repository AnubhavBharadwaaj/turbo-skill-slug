"""
Battle Trace: an experimental temporal replay of a session as a war between the
Agent and the Environment.

This is the LITERAL, time-based telling of the session — complementary to the
shell's byobu battle layer, which is the frozen, artistic telling. The shell
remembers the campaign as a folding screen; Battle Trace replays it as it
happened.

It reuses the SAME structured extraction the rest of the app already produces
(approaches, dead_ends, breakthroughs, gotchas, sentiment), so there is no
second parser and no new model call. Events map to combat:

  approach tried      -> the Agent makes a move (cmd)
  dead end            -> the Environment strikes (err): Agent resolve drops
  gotcha              -> a clash of blades (clash)
  breakthrough        -> a blow lands true (win): Environment resistance drops
  final breakthrough  -> the battle resolves (done)

The renderer is self-contained Canvas 2D (fine for session-sized traces),
sandboxed inside an iframe so it can never affect the main pipeline.
"""

from __future__ import annotations

import html
import json


def extraction_to_events(extraction: dict) -> list[dict]:
    """Convert a session extraction into an ordered Battle Trace event stream.

    Events are ordered by their position along the session (0..1) where we have
    it (dead ends, breakthroughs), and interleaved sensibly otherwise.
    """
    events: list[dict] = []

    approaches = extraction.get("approaches_tried", []) or []
    dead_ends = extraction.get("dead_ends", []) or []
    breakthroughs = extraction.get("breakthroughs", []) or []
    gotchas = extraction.get("gotchas", []) or []

    # approaches kick off near the start, spaced across the first half
    for i, a in enumerate(approaches):
        if not isinstance(a, dict):
            continue
        pos = 0.05 + (i / max(1, len(approaches))) * 0.4
        label = str(a.get("approach", "a move"))[:72]
        events.append({"pos": pos, "side": "A", "kind": "cmd", "label": label})

    # dead ends at their real positions — the Environment strikes
    for d in dead_ends:
        if not isinstance(d, dict):
            continue
        pos = float(d.get("position", 0.5))
        label = str(d.get("what_happened", "a wall"))[:72]
        events.append({"pos": pos, "side": "E", "kind": "err", "label": label})

    # gotchas as clashes, spread through the middle
    for i, g in enumerate(gotchas):
        pos = 0.3 + (i / max(1, len(gotchas))) * 0.5
        label = str(g)[:72]
        events.append({"pos": pos, "side": "A", "kind": "clash", "label": label})

    # breakthroughs at their positions — blows land
    for i, b in enumerate(breakthroughs):
        if not isinstance(b, dict):
            continue
        pos = float(b.get("position", 0.85))
        label = str(b.get("what_worked", "a breakthrough"))[:72]
        kind = "done" if i == len(breakthroughs) - 1 else "win"
        events.append({"pos": pos, "side": "A", "kind": kind, "label": label})

    events.sort(key=lambda e: e["pos"])
    # assign a monotonic time axis from positions
    for i, e in enumerate(events):
        e["t"] = round(1.0 + e["pos"] * 12.0, 2)
    if not events:
        events = [{"pos": 0.5, "side": "A", "kind": "info", "label": "a quiet session", "t": 6.0}]
    # ensure the last event resolves the battle
    if events[-1]["kind"] not in ("done", "err"):
        events[-1]["kind"] = "done"
    return events


# The renderer: a trimmed, self-contained Canvas 2D battle. No external deps.
# Events are injected as JSON; everything else is static.
_BATTLE_HTML = r"""<!DOCTYPE html><html><head><meta charset="utf-8"/>
<style>
  :root{--bg:#0a0e14;--ink:#e6edf3;--muted:#8b98a9;--agent:#6ee7ff;--env:#ff7a59;
        --ok:#7ee787;--warn:#f0c674;--magic:#d2a8ff;--line:#1c2430;}
  html,body{margin:0;height:100%;background:var(--bg);color:var(--ink);
    font-family:ui-monospace,Menlo,Consolas,monospace;overflow:hidden}
  #wrap{position:relative;height:100vh;width:100vw}
  #stage{display:block;width:100%;height:100%}
  .hud{position:absolute;top:0;left:0;right:0;padding:12px 18px;display:flex;
    justify-content:space-between;pointer-events:none;font-size:12px}
  .hud .agent{color:var(--agent);font-weight:600}.hud .env{color:var(--env);font-weight:600}
  .hud .hp{font-size:11px;color:var(--muted)}
  .caption{position:absolute;left:0;right:0;bottom:0;padding:10px 18px;
    background:linear-gradient(transparent,rgba(7,10,15,.92));font-size:12px;min-height:38px}
  .caption .t{color:var(--muted);margin-right:8px}
  .controls{position:absolute;bottom:46px;left:50%;transform:translateX(-50%);display:flex;gap:8px}
  button{background:transparent;color:var(--ink);border:1px solid var(--line);
    border-radius:8px;padding:6px 12px;font-family:inherit;font-size:12px;cursor:pointer}
  button:hover{border-color:var(--agent);color:var(--agent)}
</style></head><body>
<div id="wrap">
  <div class="hud">
    <div><span class="agent">&#x2B21; THE AGENT (you)</span><br/><span class="hp" id="hpA">resolve 100</span></div>
    <div style="text-align:right"><span class="env">THE ENVIRONMENT &#x2B21;</span><br/><span class="hp" id="hpE">resistance 100</span></div>
  </div>
  <canvas id="stage"></canvas>
  <div class="controls"><button id="replay">&#x21BB; replay the battle</button></div>
  <div class="caption"><span class="t" id="capT">t+0.0s</span><span id="capX">the slug replays the battle, from the first move...</span></div>
</div>
<script>
const EVENTS = __EVENTS_JSON__;
const C={cmd:"#6ee7ff",read:"#7ee787",clash:"#f0c674",err:"#ff7a59",retry:"#d2a8ff",win:"#7ee787",done:"#6ee7ff",info:"#8b98a9"};
const cv=document.getElementById("stage"),ctx=cv.getContext("2d");
let W=0,H=0,DPR=Math.min(2,window.devicePixelRatio||1);
function resize(){const r=cv.getBoundingClientRect();W=r.width;H=r.height;cv.width=W*DPR;cv.height=H*DPR;ctx.setTransform(DPR,0,0,DPR,0,0);}
addEventListener("resize",resize);
const stars=[];for(let i=0;i<70;i++)stars.push({x:Math.random(),y:Math.random()*0.55,r:Math.random()*1.2,a:.3+Math.random()*.5});
let particles=[],bolts=[],rings=[],markers=[],idx=0,clock=0,running=true,lastTs=0,hpA=100,hpE=100;
const span=Math.max(8,EVENTS.length?EVENTS[EVENTS.length-1].t:10);
function godA(){return{x:W*0.12,y:H*0.54}}function godE(){return{x:W*0.88,y:H*0.54}}
function spark(x,y,c,n){for(let i=0;i<n;i++){const a=Math.random()*6.28,s=40+Math.random()*120;particles.push({x,y,vx:Math.cos(a)*s,vy:Math.sin(a)*s,life:1,color:c,size:1.5+Math.random()*2})}}
function bolt(f,t,c){bolts.push({from:f,to:t,color:c,life:1})}
function ring(x,y,c){rings.push({x,y,r:18,color:c,life:1})}
function play(ev){const a=godA(),e=godE();const mx=W*0.5+(ev.t/span-0.5)*W*0.12,my=H*0.46+(Math.random()*40-20);
  const src=ev.side==="A"?a:e;ring(src.x,src.y,C[ev.kind]);bolt(src,{x:mx,y:my},C[ev.kind]);
  if(["clash","err","win","done"].includes(ev.kind))setTimeout(()=>spark(mx,my,C[ev.kind],ev.kind==="done"?30:16),130);
  if(ev.kind==="err")hpA=Math.max(0,hpA-12);if(ev.kind==="clash")hpE=Math.max(0,hpE-8);
  if(ev.kind==="win"||ev.kind==="done")hpE=Math.max(0,hpE-15);
  markers.push({t:ev.t,color:C[ev.kind],r:0});
  document.getElementById("hpA").textContent="resolve "+Math.round(hpA);
  document.getElementById("hpE").textContent="resistance "+Math.round(hpE);
  document.getElementById("capT").textContent="t+"+ev.t.toFixed(1)+"s";
  document.getElementById("capX").textContent=ev.label;}
function god(g,c,l){const gr=ctx.createRadialGradient(g.x,g.y,4,g.x,g.y,54);gr.addColorStop(0,c+"99");gr.addColorStop(1,c+"00");
  ctx.fillStyle=gr;ctx.beginPath();ctx.arc(g.x,g.y,54,0,7);ctx.fill();
  ctx.fillStyle="#0a0e14";ctx.strokeStyle=c;ctx.lineWidth=2;ctx.beginPath();ctx.arc(g.x,g.y,24,0,7);ctx.fill();ctx.stroke();
  ctx.fillStyle=c;ctx.font="600 22px ui-monospace,monospace";ctx.textAlign="center";ctx.textBaseline="middle";ctx.fillText(l,g.x,g.y+1);}
function frame(ts){if(!lastTs)lastTs=ts;const dt=Math.min(0.05,(ts-lastTs)/1000);lastTs=ts;
  if(running){clock+=dt;while(idx<EVENTS.length&&EVENTS[idx].t<=clock){play(EVENTS[idx]);idx++;}
    if(idx>=EVENTS.length&&particles.length===0&&bolts.length===0)running=false;}
  ctx.clearRect(0,0,W,H);
  for(const s of stars){ctx.globalAlpha=s.a;ctx.fillStyle="#fff";ctx.fillRect(s.x*W,s.y*H,s.r,s.r);}ctx.globalAlpha=1;
  const y0=H*0.84,x0=W*0.1,x1=W*0.9,g=ctx.createLinearGradient(x0,0,x1,0);g.addColorStop(0,"#6ee7ff");g.addColorStop(1,"#ff7a59");
  ctx.strokeStyle=g;ctx.globalAlpha=.45;ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(x0,y0);ctx.lineTo(x1,y0);ctx.stroke();ctx.globalAlpha=1;
  for(const m of markers){m.r=Math.min(4,m.r+dt*16);const mx=x0+(m.t/span)*(x1-x0);ctx.fillStyle=m.color;ctx.beginPath();ctx.arc(mx,y0,m.r,0,7);ctx.fill();}
  god(godA(),"#6ee7ff","A");god(godE(),"#ff7a59","E");
  for(let i=bolts.length-1;i>=0;i--){const b=bolts[i];b.life-=dt*4;if(b.life<=0){bolts.splice(i,1);continue;}
    ctx.strokeStyle=b.color;ctx.globalAlpha=Math.max(0,b.life);ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(b.from.x,b.from.y);
    const mx=(b.from.x+b.to.x)/2+(Math.random()*8-4),my=(b.from.y+b.to.y)/2+(Math.random()*8-4);ctx.quadraticCurveTo(mx,my,b.to.x,b.to.y);ctx.stroke();ctx.globalAlpha=1;}
  for(let i=rings.length-1;i>=0;i--){const r=rings[i];r.r+=dt*90;r.life-=dt*1.8;if(r.life<=0){rings.splice(i,1);continue;}
    ctx.strokeStyle=r.color;ctx.globalAlpha=Math.max(0,r.life);ctx.lineWidth=2;ctx.beginPath();ctx.arc(r.x,r.y,r.r,0,7);ctx.stroke();ctx.globalAlpha=1;}
  for(let i=particles.length-1;i>=0;i--){const p=particles[i];p.life-=dt*1.5;p.vy+=dt*30;p.x+=p.vx*dt;p.y+=p.vy*dt;
    if(p.life<=0){particles.splice(i,1);continue;}ctx.fillStyle=p.color;ctx.globalAlpha=Math.max(0,p.life);ctx.fillRect(p.x,p.y,p.size,p.size);ctx.globalAlpha=1;}
  requestAnimationFrame(frame);}
document.getElementById("replay").onclick=()=>{idx=0;clock=0;hpA=100;hpE=100;particles=[];bolts=[];rings=[];markers=[];running=true;lastTs=0;};
resize();requestAnimationFrame(frame);
</script></body></html>"""


def render_battle_trace(extraction: dict, height: int = 420) -> str:
    """Return an iframe hosting the Battle Trace replay for this extraction.

    Sandboxed iframe so it cannot affect the main app. Best-effort: any failure
    returns an empty string and the accordion simply shows nothing.
    """
    try:
        events = extraction_to_events(extraction)
        doc = _BATTLE_HTML.replace("__EVENTS_JSON__", json.dumps(events))
        escaped = html.escape(doc, quote=True)
        return (
            f'<iframe srcdoc="{escaped}" '
            f'style="width:100%;height:{height}px;border:1px solid #1c2430;'
            f'border-radius:10px;background:#0a0e14;" '
            f'sandbox="allow-scripts"></iframe>'
        )
    except Exception:
        return ""
