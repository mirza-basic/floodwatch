"""Render the snapshot into one self-contained HTML map.

The snapshot and the light boundaries are inlined so the page works from
file:// with no server, the same first-paint approach as fire-detection. Colours
run blue -> violet -> magenta on purpose: flood levels must not read as the
orange/red fire severity scale if both maps are ever open side by side.
"""
from __future__ import annotations

import json

from . import config

PAGE = r"""<!doctype html>
<html lang="bs"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>FloodWatch BiH</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
:root{--bg:#fff;--fg:#17212b;--mut:#5b6b7a;--line:#d5dde5}
@media (prefers-color-scheme:dark){:root{--bg:#161d25;--fg:#e6edf3;--mut:#93a4b5;--line:#2b3744}}
html,body,#map{height:100%;margin:0}body{font:14px system-ui,sans-serif;background:var(--bg);color:var(--fg)}
.panel{position:absolute;z-index:1000;top:10px;right:10px;width:250px;max-height:calc(100% - 20px);overflow:auto;
 background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:10px 12px;box-shadow:0 2px 8px #0003}
.panel h1{font-size:15px;margin:0 0 2px}.mut{color:var(--mut);font-size:12px}
.row{display:flex;align-items:center;gap:8px;margin:5px 0;cursor:default}
.dot{width:12px;height:12px;border-radius:50%;flex:none}
.item{padding:4px 0;border-top:1px solid var(--line);cursor:pointer}
.lang{float:right;cursor:pointer;border:1px solid var(--line);border-radius:4px;padding:0 6px;font-size:12px}
.leaflet-popup-content{margin:10px 12px;min-width:210px}.pop b{font-size:15px}
@media (max-width:600px){.panel{width:auto;left:10px;max-height:38%}}
</style></head><body><div id="map"></div>
<div class="panel"><span class="lang" id="lang"></span><h1 id="title"></h1>
<div class="mut" id="stamp"></div><div id="legend"></div><div id="list"></div></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const SNAP=__SNAPSHOT__, BOUNDS=__BOUNDS__, RIV=__RIVERS__;
const LV=["normal","watch","warning","severe"];
const COL={normal:"#8fa6bb",watch:"#4f9de0",warning:"#6a3fd1",severe:"#a3188f"};
const I18N={
 bs:{title:"FloodWatch BiH",upd:"Ažurirano",normal:"Normalno",watch:"Pažnja",warning:"Upozorenje",severe:"Opasnost",
  now:"Sada",peak:"Vrhunac",flow:"Protok (m³/s)",noriver:"Nema značajnog vodotoka u modelu",
  none:"Nema upozorenja u narednih 7 dana",note:"Prognoza modela GloFAS (~5 km), ne mjerenje vodostaja.",lang:"EN"},
 en:{title:"FloodWatch BiH",upd:"Updated",normal:"Normal",watch:"Watch",warning:"Warning",severe:"Severe",
  now:"Now",peak:"Peak",flow:"Discharge (m³/s)",noriver:"No significant river in the model",
  none:"No warnings in the next 7 days",note:"GloFAS model forecast (~5 km), not a gauge reading.",lang:"BS"}};
let lang=null;try{lang=localStorage.getItem("fl_lang")}catch(e){}
lang=lang==="en"?"en":"bs";
const t=k=>I18N[lang][k]||k;
const map=L.map("map",{zoomControl:true}).fitBounds([[42.5,15.7],[45.3,19.7]],{animate:false});
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:18,attribution:"© OpenStreetMap"}).addTo(map);
const polys=L.layerGroup().addTo(map), lines=L.layerGroup().addTo(map), dots=L.layerGroup().addTo(map);

function spark(m){
  const f=m.flows, n=f.length, W=210, H=70, th=m.thresholds;
  const top=Math.max(...f.filter(v=>v!=null),th.watch)*1.1||1;
  const x=i=>6+i*(W-12)/(n-1), y=v=>H-4-(H-10)*v/top;
  const todayI=m.times.indexOf(SNAP.today);
  let s=`<svg width="${W}" height="${H}" role="img" aria-label="${t("flow")}">`;
  for(const k of ["watch","warning","severe"]) if(th[k]<=top)
    s+=`<line x1="0" x2="${W}" y1="${y(th[k])}" y2="${y(th[k])}" stroke="${COL[k]}" stroke-dasharray="3 3" opacity=".7"/>`;
  if(todayI>=0) s+=`<line x1="${x(todayI)}" x2="${x(todayI)}" y1="0" y2="${H}" stroke="currentColor" opacity=".25"/>`;
  s+=`<polyline fill="none" stroke="${COL[m.level]}" stroke-width="2" points="${f.map((v,i)=>v==null?"":x(i)+","+y(v)).join(" ")}"/></svg>`;
  return s;
}
function riverBlock(r){
  return `<div style="margin-top:6px"><b>${r.river||""}</b> <span style="color:${COL[r.level]}">● ${t(r.level)}</span>
   <div class="mut">${t("now")}: ${r.now??"–"} m³/s · ${t("peak")}: ${r.peak} (${r.peak_day})</div>${spark(r)}</div>`;
}
function popup(m,r){
  if(!m.rivers.length) return `<div class="pop"><b>${m.name}</b><br>${t("noriver")}</div>`;
  const rs=r?[r]:m.rivers;
  return `<div class="pop"><b>${m.name}</b>${rs.map(riverBlock).join("")}<div class="mut" style="margin-top:6px">${t("note")}</div></div>`;
}
function draw(){
  polys.clearLayers(); lines.clearLayers(); dots.clearLayers();
  const seen={}; const worst=[];
  for(const m of SNAP.municipalities){
    const rings=BOUNDS[m.id]; if(!rings) continue;
    const up=m.level!=="normal";
    const p=L.polygon(rings,{color:COL[m.level],weight:up?2:.8,opacity:up?.9:.5,
      fillColor:COL[m.level],fillOpacity:up?.35:.03}).addTo(polys);
    p.bindPopup(()=>popup(m),{autoPan:false});
    for(const r of m.rivers){
      const g=(RIV[m.id]||[]).find(x=>x.name===r.river);
      const ru=r.level!=="normal";
      if(g&&g.lines.length)
        L.polyline(g.lines,{color:COL[r.level],weight:ru?5:2,opacity:ru?.95:.6,lineCap:"round"})
          .addTo(lines).bindPopup(()=>popup(m,r),{autoPan:false});
      const at=g?[g.mlat,g.mlon]:[r.lat,r.lon];
      const key=at+","+r.level; if(seen[key]) continue; seen[key]=1;
      L.circleMarker(at,{radius:ru?9:4,color:"#fff",weight:1.5,fillColor:COL[r.level],fillOpacity:.95})
        .addTo(dots).bindPopup(()=>popup(m,r),{autoPan:false});
    }
    if(up) worst.push(m);
  }
  const pk=m=>m.rivers.length?Math.max(...m.rivers.map(r=>r.peak||0)):0;
  worst.sort((a,b)=>LV.indexOf(b.level)-LV.indexOf(a.level)||pk(b)-pk(a));
  const c={}; SNAP.municipalities.forEach(m=>c[m.level]=(c[m.level]||0)+1);
  document.getElementById("title").textContent=t("title");
  document.getElementById("lang").textContent=t("lang");
  document.getElementById("stamp").textContent=t("upd")+": "+SNAP.generated_at.replace("T"," ").slice(0,16)+" UTC";
  document.getElementById("legend").innerHTML=LV.map(k=>`<div class="row"><span class="dot" style="background:${COL[k]}"></span>${t(k)} <span class="mut">(${c[k]||0})</span></div>`).join("");
  document.getElementById("list").innerHTML=worst.length?worst.map((m,i)=>`<div class="item" data-i="${i}"><span style="color:${COL[m.level]}">●</span> ${m.name} <span class="mut">${m.rivers.filter(r=>r.level===m.level).map(r=>r.river||"").filter(Boolean).join(", ")} · ${pk(m)} m³/s</span></div>`).join(""):`<div class="mut" style="margin-top:8px">${t("none")}</div>`;
  document.querySelectorAll(".item").forEach(el=>el.onclick=()=>{const m=worst[+el.dataset.i];
    const r0=m.rivers[0],g0=(RIV[m.id]||[]).find(x=>x.name===r0.river),at=g0?[g0.mlat,g0.mlon]:[r0.lat,r0.lon];map.setView(at,10,{animate:false});L.popup({autoPan:false}).setLatLng(at).setContent(popup(m)).openOn(map)});
}
document.getElementById("lang").onclick=()=>{lang=lang==="bs"?"en":"bs";try{localStorage.setItem("fl_lang",lang)}catch(e){}draw()};
draw();
</script></body></html>"""


def render(snapshot: dict) -> str:
    bounds = json.loads((config.DATA_DIR / "boundaries-simple.json").read_text())
    rivers: dict[str, list] = {}
    if config.POINTS_FILE.exists():
        for p in json.loads(config.POINTS_FILE.read_text()):
            if p.get("mlat") is not None:
                rivers.setdefault(p["id"], []).append(
                    {"name": p["river_name"], "mlat": p["mlat"], "mlon": p["mlon"], "lines": p["lines"]})
    return (PAGE.replace("__SNAPSHOT__", json.dumps(snapshot, ensure_ascii=False))
                .replace("__RIVERS__", json.dumps(rivers, ensure_ascii=False, separators=(",", ":")))
                .replace("__BOUNDS__", json.dumps(bounds, separators=(",", ":"))))
