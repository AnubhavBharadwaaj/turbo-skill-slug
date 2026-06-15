"""
Shell3D renderer: the nautilus as a real 3D object with iridescent nacre.

Consumes a SceneGraph and emits a self-contained Three.js scene (in an iframe) that
the user can orbit. The shell GEOMETRY is generated from ShellState (turns, growth,
knots, aperture) so it stays traceable; the MATERIAL is a real physically-based
iridescent surface (mother-of-pearl) whose strength comes from ShellState.iridescence
and whose colours come from the emotional palette. Knots (dead ends) become raised
nubs on the shell body; the aperture (breakthrough) glows.

No API key, no build step: Three.js is loaded from a CDN inside the iframe. WebGL is
the only requirement; available() reports that honestly.
"""

from __future__ import annotations

import html as _html
import json

from scene_graph import SceneGraph


class Shell3DRenderer:
    id = "shell3d"
    label = "The shell, in 3D"
    description = "Your nautilus as a real object you can turn in the light — iridescent nacre."
    supported_versions = ("1.0",)
    requires_generation = False

    def available(self) -> tuple[bool, str]:
        # Always offerable; WebGL support is a client-side capability we cannot
        # detect server-side. The iframe degrades to a message if WebGL is absent.
        return (True, "")

    def render(self, scene: SceneGraph) -> dict:
        params = {
            "turns": scene.shell.turns,
            "growth": scene.shell.growth_curve,
            "knots": scene.shell.knots,
            "jewels": scene.shell.jewels,
            "aperture": scene.shell.aperture,
            "iridescence": scene.shell.iridescence,
            "palette": scene.shell.palette,
            "session": scene.session_id,
        }
        doc = _THREE_DOC.replace("__PARAMS__", json.dumps(params))
        escaped = _html.escape(doc, quote=True)
        iframe = (
            f'<iframe srcdoc="{escaped}" '
            f'style="width:100%;height:560px;border:none;border-radius:12px;'
            f'background:#07090d;" sandbox="allow-scripts allow-downloads"></iframe>'
        )
        return {"kind": "iframe", "html": iframe, "notes": ""}


# The Three.js scene. A log-spiral tube of growing radius (the nautilus), with a
# real iridescent material (KHR-style thin-film via onBeforeCompile is heavy; we
# use MeshPhysicalMaterial.iridescence which three r150+ supports natively), knots
# as small spheres on the centerline, and a glowing aperture sphere at the tip.
_THREE_DOC = r"""<!DOCTYPE html><html><head><meta charset="utf-8"/>
<style>
  html,body{margin:0;height:100%;background:#07090d;overflow:hidden}
  #fallback{color:#9aa;font:14px ui-monospace,monospace;padding:18px}
  #hint{position:fixed;left:12px;bottom:10px;color:#8a93a3;
    font:11px ui-monospace,monospace;opacity:.7;pointer-events:none}
</style></head><body>
<div id="fallback" style="display:none">This lens needs WebGL, which your browser
or device did not provide. Try a desktop browser to turn the shell in 3D.</div>
<div id="hint">drag to orbit · scroll to zoom</div>
<div id="ctl" style="position:fixed;right:12px;top:12px;display:flex;gap:8px;z-index:10">
  <button id="resetBtn" style="font:11px ui-monospace,monospace;color:#cfe3ff;
    background:rgba(20,28,40,.72);border:1px solid #2a3a52;border-radius:8px;
    padding:6px 10px;cursor:pointer">reset view</button>
  <button id="shotBtn" style="font:11px ui-monospace,monospace;color:#ffe9c2;
    background:rgba(20,28,40,.72);border:1px solid #5a4a2a;border-radius:8px;
    padding:6px 10px;cursor:pointer">save image</button>
</div>
<script type="importmap">
{ "imports": {
  "three": "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js"
}}
</script>
<script type="module">
import * as THREE from "three";
const P = __PARAMS__;

function fail(){ document.getElementById("fallback").style.display="block";
  document.getElementById("hint").style.display="none"; }

let renderer;
try {
  renderer = new THREE.WebGLRenderer({antialias:true, alpha:true, preserveDrawingBuffer:true});
} catch(e){ fail(); throw e; }
if(!renderer || !renderer.getContext()){ fail(); }

renderer.setSize(innerWidth, innerHeight);
renderer.setPixelRatio(Math.min(2, devicePixelRatio||1));
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(45, innerWidth/innerHeight, 0.1, 100);
camera.position.set(0, 0.6, 6);

// ---- lighting: a key, a warm rim, and an environment for the iridescence ----
scene.add(new THREE.AmbientLight(0x223044, 0.6));
const key = new THREE.DirectionalLight(0xffffff, 2.0); key.position.set(4,6,5); scene.add(key);
const rim = new THREE.DirectionalLight(0xffd9a0, 1.4); rim.position.set(-5,-2,-3); scene.add(rim);
const tealL = new THREE.DirectionalLight(0x66e0ff, 1.0); tealL.position.set(-3,4,2); scene.add(tealL);
const magL  = new THREE.PointLight(0xff8adf, 1.4, 12); magL.position.set(2,-3,3); scene.add(magL);
// a simple gradient environment so the nacre has something to refract
const pmrem = new THREE.PMREMGenerator(renderer);
const envScene = new THREE.Scene();
const grad = new THREE.Mesh(
  new THREE.SphereGeometry(50,32,32),
  new THREE.ShaderMaterial({side:THREE.BackSide, uniforms:{},
    vertexShader:`varying vec3 v; void main(){ v=position; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0);}`,
    fragmentShader:`varying vec3 v; void main(){ float t=normalize(v).y*0.5+0.5;
      vec3 a=vec3(0.06,0.10,0.18), b=vec3(0.45,0.40,0.55); float band=0.5+0.5*sin(normalize(v).x*8.0); vec3 col=mix(a,b,t)+band*vec3(0.10,0.06,0.14); gl_FragColor=vec4(col,1.0);}`}));
envScene.add(grad);
const envTex = pmrem.fromScene(envScene).texture;
scene.environment = envTex;

// ---- palette from the emotional arc ----
const startC = new THREE.Color(P.palette.start_hex);
const endC   = new THREE.Color(P.palette.end_hex);
const accent = new THREE.Color(P.palette.accent_hex);

// ---- build the nautilus as a tube along a log spiral of growing radius ----
const TURNS = Math.max(1, P.turns);
const TOTAL = TURNS * Math.PI * 2;
const b = 0.13;                         // tighter -> whorls nearly touch
const pts = [];
const N = 400;
for(let i=0;i<=N;i++){
  const t = i/N;
  const ang = t * TOTAL;
  const r = 0.10 * Math.exp(b*ang);     // log spiral radius
  const x = Math.cos(ang)*r;
  const y = Math.sin(ang)*r;
  const z = (t-0.5)*0.5*r;              // slight conical rise -> 3D shell
  pts.push(new THREE.Vector3(x,y,z));
}
const curve = new THREE.CatmullRomCurve3(pts);
// tube radius grows along the arm (the shell body thickens outward)
const tubeR = 0.20;
const geo = new THREE.TubeGeometry(curve, 600, tubeR, 24, false);
// taper the tube: scale each ring by its position along the arm
const pos = geo.attributes.position;
const tmp = new THREE.Vector3();
for(let i=0;i<pos.count;i++){
  // approximate t by ring index
  const ring = Math.floor(i/ (24+1));
  const t = ring/600;
  const grow = 0.12 + 2.4*t*t;          // fat rounded body whorl at the rim
  tmp.fromBufferAttribute(pos,i);
  // pull toward centerline point then push out scaled
  const cp = curve.getPoint(Math.min(1,t));
  tmp.sub(cp).multiplyScalar(grow).add(cp);
  pos.setXYZ(i, tmp.x, tmp.y, tmp.z);
}
geo.computeVertexNormals();

// ---- vertex-colored gradient along the arm (start -> end sentiment) ----
const colors = [];
for(let i=0;i<pos.count;i++){
  const ring = Math.floor(i/(24+1));
  const t = Math.min(1, ring/600);
  const c = startC.clone().lerp(endC, t);
  colors.push(c.r,c.g,c.b);
}
geo.setAttribute("color", new THREE.Float32BufferAttribute(colors,3));

// ---- iridescent nacre material ----
const mat = new THREE.MeshPhysicalMaterial({
  vertexColors:true,
  metalness:0.05, roughness:0.18,
  clearcoat:1.0, clearcoatRoughness:0.18,
  iridescence: Math.max(0.55, P.iridescence),
  iridescenceIOR:1.6,
  iridescenceThicknessRange:[200, 900],
  envMapIntensity:1.6,
  sheen:0.6, sheenColor:accent,
});
const shell = new THREE.Mesh(geo, mat);
scene.add(shell);

// ---- knots: raised nubs at each dead-end position along the arm ----
const knotMat = new THREE.MeshPhysicalMaterial({color:0x2a1d12, roughness:0.3, clearcoat:1.0, iridescence:0.8, iridescenceIOR:1.4});
for(const k of (P.knots||[])){
  const cp = curve.getPoint(Math.min(1, k.t));
  const s = new THREE.Mesh(new THREE.SphereGeometry(0.10+0.06*(k.severity||0.5),20,20), knotMat);
  s.position.copy(cp); shell.add(s);
}

// ---- jewels: iridescent beads on the rim at each gotcha position ----
// gotchas sit "along the rim", so offset each bead outward from the centerline
// along the local radial direction (from shell center to the curve point).
const jewelMat = new THREE.MeshPhysicalMaterial({
  color: accent.clone().lerp(new THREE.Color(0xffffff), 0.35),
  metalness:0.0, roughness:0.12, clearcoat:1.0, clearcoatRoughness:0.1,
  iridescence:1.0, iridescenceIOR:1.5, iridescenceThicknessRange:[150,700],
  envMapIntensity:1.8,
});
for(const j of (P.jewels||[])){
  const cp = curve.getPoint(Math.min(1, j.t));
  // radial direction in the shell's xy-plane (the spiral grows outward in xy)
  const radial = new THREE.Vector3(cp.x, cp.y, 0);
  if(radial.lengthSq() < 1e-6) radial.set(1,0,0); else radial.normalize();
  const bead = new THREE.Mesh(new THREE.SphereGeometry(0.085,18,18), jewelMat);
  // local tube radius grows along the arm; push the bead just past the surface
  const localGrow = 0.12 + 2.4*j.t*j.t;
  const off = tubeR*localGrow + 0.05;
  bead.position.copy(cp).addScaledVector(radial, off);
  shell.add(bead);
}

// ---- aperture: a glowing sphere at the breakthrough position ----
const ap = P.aperture||{t:0.95,intensity:0.8};
const apPos = curve.getPoint(Math.min(1, ap.t));
const apMat = new THREE.MeshBasicMaterial({color:accent});
const apMesh = new THREE.Mesh(new THREE.SphereGeometry(0.12+0.12*ap.intensity,24,24), apMat);
apMesh.position.copy(apPos); shell.add(apMesh);
const apLight = new THREE.PointLight(accent.getHex(), 2.0*ap.intensity, 4);
apLight.position.copy(apPos); shell.add(apLight);

// frame the shell
const box = new THREE.Box3().setFromObject(shell);
const center = box.getCenter(new THREE.Vector3());
shell.position.sub(center);
const size = box.getSize(new THREE.Vector3()).length();
camera.position.set(0, size*0.15, size*1.1);
camera.lookAt(0,0,0);

// ---- minimal orbit controls (no extra dependency) ----
let drag=false, px=0, py=0, rotY=0.2, rotX=-0.15, dist=size*1.1;
const el = renderer.domElement;
el.addEventListener("pointerdown", e=>{drag=true;px=e.clientX;py=e.clientY;});
addEventListener("pointerup", ()=>drag=false);
addEventListener("pointermove", e=>{ if(!drag)return;
  rotY += (e.clientX-px)*0.008; rotX += (e.clientY-py)*0.008;
  rotX=Math.max(-1.2,Math.min(1.2,rotX)); px=e.clientX; py=e.clientY; });
el.addEventListener("wheel", e=>{ dist*=(1+Math.sign(e.deltaY)*0.08);
  dist=Math.max(size*0.5,Math.min(size*3,dist)); e.preventDefault(); }, {passive:false});

// pinch-zoom: two-finger distance drives the same `dist` as the wheel
let pinchD = 0;
el.addEventListener("touchstart", e=>{
  if(e.touches.length===2){
    const dx=e.touches[0].clientX-e.touches[1].clientX;
    const dy=e.touches[0].clientY-e.touches[1].clientY;
    pinchD = Math.hypot(dx,dy);
    drag = false;            // suppress orbit while pinching
  }
}, {passive:false});
el.addEventListener("touchmove", e=>{
  if(e.touches.length===2 && pinchD>0){
    const dx=e.touches[0].clientX-e.touches[1].clientX;
    const dy=e.touches[0].clientY-e.touches[1].clientY;
    const d = Math.hypot(dx,dy);
    const ratio = pinchD / Math.max(1,d);     // fingers apart -> zoom in
    dist *= ratio;
    dist = Math.max(size*0.5, Math.min(size*3, dist));
    pinchD = d;
    e.preventDefault();
  }
}, {passive:false});
el.addEventListener("touchend", e=>{ if(e.touches.length<2) pinchD=0; });

addEventListener("resize", ()=>{ camera.aspect=innerWidth/innerHeight;
  camera.updateProjectionMatrix(); renderer.setSize(innerWidth,innerHeight); });

// ---- Tier 1: reset view ----
// capture the framing defaults so reset restores the exact initial pose
const DEF_rotY = rotY, DEF_rotX = rotX, DEF_dist = dist;
const resetBtn = document.getElementById("resetBtn");
if (resetBtn) resetBtn.addEventListener("click", ()=>{
  rotY = DEF_rotY; rotX = DEF_rotX; dist = DEF_dist;
});

// ---- Tier 1: save image (screenshot) ----
// WebGL clears its drawing buffer after render, so toDataURL() on a stale frame
// is blank. We render ONE fresh frame immediately before reading the pixels, in
// the same tick, which captures correctly without preserveDrawingBuffer.
const shotBtn = document.getElementById("shotBtn");
if (shotBtn) shotBtn.addEventListener("click", ()=>{
  try {
    renderer.render(scene, camera);              // fresh frame, same tick
    const url = renderer.domElement.toDataURL("image/png");
    const a = document.createElement("a");
    a.href = url;
    a.download = "turboskillslug-shell-" + (P.session || "session") + ".png";
    document.body.appendChild(a); a.click(); a.remove();
  } catch (e) {
    // never break the lens if capture fails (some browsers block tainted canvases)
    console.warn("screenshot failed:", e);
  }
});

function loop(){
  requestAnimationFrame(loop);
  // gentle auto-spin when idle, plus user orbit
  if(!drag) rotY += 0.0016;
  const cx=Math.sin(rotY)*Math.cos(rotX)*dist;
  const cy=Math.sin(rotX)*dist;
  const cz=Math.cos(rotY)*Math.cos(rotX)*dist;
  camera.position.set(cx,cy,cz); camera.lookAt(0,0,0);
  renderer.render(scene, camera);
}
loop();
</script></body></html>"""
