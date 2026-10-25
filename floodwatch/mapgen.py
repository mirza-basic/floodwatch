"""Render the snapshot into one self-contained HTML map.

The layout deliberately mirrors FireWatch's: a docked side panel (status header,
day chips, source pills, cards), map tools on the left, language switch on top, a
collapsible legend, and a bottom bar - which here scrubs forecast *days* where
FireWatch scrubs hours. The stylesheet (`ui.css`) is FireWatch's with a blue accent
and flood colours; the markup keeps its ids so the two stay visually one family.

The snapshot, light boundaries and river lines are inlined so the page needs no
server beyond the Referer rule in __main__ (see there): the same first-paint
approach as fire-detection. Colours run blue -> violet -> magenta on purpose, so
flood levels never read as FireWatch's orange/red fire scale.

Level per day is computed in the browser from each river's daily flows and
thresholds (the same comparison levels.classify makes), so the day chips, the
timeline and the 7-day "peak" view all agree with the server's own peak level.
"""
from __future__ import annotations

import json

from . import config

CSS = (config.ROOT / "floodwatch" / "ui.css").read_text(encoding="utf8")

EXTRA_CSS = r"""
  /* ---- FloodWatch additions on top of the shared stylesheet ---- */
  :root{--normal:#1fb5a6;--watch:#4aa8ff;--warning:#8b6cff;--severe:#e0489f}
  .leaflet-container{background:#0b0e12;font:inherit}
  .leaflet-bar a{background:#151a21;color:#e6edf3;border-bottom:1px solid #28313d}
  .leaflet-bar a:hover{background:#1c232c}
  .tool{display:flex;align-items:center;justify-content:center;width:30px;height:30px;
    background:#151a21;border:1px solid #28313d;border-radius:4px;color:#e6edf3;cursor:pointer;
    font-size:15px;box-shadow:0 1px 5px rgba(0,0,0,.45);margin-top:8px}
  .tool.off{color:#6b7785}
  #layersbtn{position:absolute;top:10px;right:10px;z-index:1000;background:rgba(21,26,33,.94);
    border:1px solid var(--line);color:var(--fg);border-radius:9px;padding:8px 13px;font:inherit;
    font-size:12.5px;cursor:pointer;backdrop-filter:blur(8px)}
  #layerspanel{position:absolute;top:50px;right:10px;z-index:1000;display:none;min-width:200px;
    background:rgba(21,26,33,.97);border:1px solid var(--line);border-radius:9px;padding:10px 12px;
    font-size:12.5px;backdrop-filter:blur(8px)}
  #layerspanel.open{display:block}
  #layerspanel label{display:flex;gap:8px;align-items:center;padding:4px 0;cursor:pointer}
  #days{display:flex;gap:4px;flex:1 1 auto;min-width:0;overflow-x:auto}
  #days button{flex:1 0 auto;min-width:46px;background:#101720;border:1px solid var(--line);color:var(--dim);
    border-radius:6px;height:34px;cursor:pointer;font:inherit;font-size:11px;line-height:1.15;padding:0 6px}
  #days button b{display:block;font-size:12px;color:var(--fg)}
  #days button.on{border-color:var(--accent);color:#fff;box-shadow:0 0 0 1px var(--accent) inset}
  #days button i{display:block;height:3px;border-radius:2px;margin:2px 0 0}
  .legend-body i.sq{border-radius:2px}
  .ev .sev.lv-watch{background:rgba(74,168,255,.18);color:var(--watch)}
  .ev .sev.lv-warning{background:rgba(139,108,255,.2);color:var(--warning)}
  .ev .sev.lv-severe{background:rgba(224,72,159,.2);color:var(--severe)}
  .ratio{height:5px;background:#101720;border-radius:3px;margin-top:8px;overflow:hidden}
  .ratio span{display:block;height:100%;border-radius:3px}
  .sechd{font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--dim);margin:12px 4px 7px}
  .ok{color:#3fb950}
  #muniinfo .rv{margin-top:10px;padding-top:8px;border-top:1px solid var(--line)}
  #muniinfo .rv:first-of-type{border-top:0;margin-top:4px;padding-top:0}
  #muniinfo .mut{color:var(--dim);font-size:12px}
  a.docs{display:block;text-align:center;text-decoration:none;color:#fff;font-weight:600;font-size:13px;
    background:var(--accent);border-radius:8px;padding:9px 12px;margin-top:12px}
  a.docs:empty,#chbtn:empty{display:none}
  #muniinfo a.more{display:block;margin-top:10px;color:var(--accent);font-size:12.5px;text-decoration:none}
  #muniinfo a.more:hover{text-decoration:underline}
  .fchart{display:block;width:100%;height:auto;margin-top:8px}
  .strip{display:flex;gap:3px;margin-top:8px}
  .strip .cell{flex:1;min-width:0;background:#101720;border:1px solid var(--line);border-radius:5px;padding:2px;cursor:pointer;font:inherit;color:inherit}
  .strip .cell.on{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent) inset}
  .strip .cell i{display:block;height:12px;border-radius:3px}
  .strip .cell b{display:block;height:4px;border-radius:2px;margin-top:2px}
  .strip .cell span{display:block;font-size:9px;color:var(--dim);text-align:center;margin-top:2px}
  #tip{position:fixed;z-index:4000;display:none;pointer-events:none;background:#151a21;color:#e6edf3;border:1px solid #3a4655;
    border-radius:6px;padding:6px 9px;font-size:11.5px;line-height:1.5;box-shadow:0 4px 14px rgba(0,0,0,.5);max-width:240px}
  /* wide enough for the chart's axis labels to stay apart */
  #muniinfo{max-width:min(430px,calc(100vw - 24px));width:min(430px,calc(100vw - 24px))}
  .gsq{width:18px;height:18px;border:3px solid #111;box-sizing:border-box}
"""

TEMPLATE = r"""<!doctype html>
<html lang="bs"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FloodWatch Bosna i Hercegovina</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='14' fill='%230F172A'/%3E%3Cpath d='M32 10C32 10 16 30 16 40a16 16 0 0 0 32 0C48 30 32 10 32 10z' fill='%235b8cff'/%3E%3C/svg%3E">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
__CSS__
</style></head><body>
<div id="loading" role="status" aria-live="polite">
  <div class="ldwrap">
    <div class="ldscene" aria-hidden="true">
      <svg viewBox="0 0 64 64" width="96" height="96"><path d="M32 8C32 8 15 29 15 40a17 17 0 0 0 34 0C49 29 32 8 32 8z" fill="#5b8cff"/></svg>
    </div>
    <div class="ldsub" id="ldsub">Loading map&hellip;</div>
  </div>
</div>
<button id="drawer-btn" aria-controls="side" aria-expanded="false" aria-label="Show list">
  <span aria-hidden="true">&#9776;</span><span id="drawer-label">Rijeke</span><span id="drawer-badge"></span>
</button>
<div id="backdrop"></div>
<div id="langsw" role="group" aria-label="Language / Jezik">
  <button data-l="bs" type="button">BS</button><button data-l="en" type="button">EN</button>
</div>
<div id="muniinfo" role="dialog"><button class="miclose" aria-label="Close" type="button">&times;</button><div id="muniinfo-body"></div></div>
<div id="wrap">
  <div id="side">
    <header>
      <button id="drawer-close" aria-label="Close list">&times;</button>
      <h1><span class="dot" id="hdot"></span><span id="htitle">FloodWatch</span></h1>
      <div class="sub" id="hsub"></div>
      <div class="seg" id="hrange"></div>
      <div class="status" id="hchips"></div>
      <a id="chbtn" class="docs" target="_blank" rel="noopener"></a>
    </header>
    <div id="list"></div>
    <footer id="foot"></footer>
  </div>
  <div id="map"></div>
  <button id="layersbtn" type="button">Slojevi</button>
  <div id="layerspanel"></div>
  <div id="timebar">
    <button id="play" title="Animate">&#9654;</button>
    <button id="speed" title="Playback speed">1&times;</button>
    <div id="days" role="group" aria-label="Forecast days"></div>
    <span id="tlabel"></span>
  </div>
</div>
<script>
const SNAP=__SNAPSHOT__, BOUNDS=__BOUNDS__, RIV=__RIVERS__, FILL=__FILL__;
const LV=["normal","watch","warning","severe"];
const COL={normal:"#1fb5a6",watch:"#4aa8ff",warning:"#8b6cff",severe:"#e0489f"};
const GCOL={N:"#7CFC00",P:"#00B0F0",R:"#FFFF00",V:"#FFC000",Z:"#F00000"};
const GSRC={sava:"Agencija za vodno područje rijeke Save",rhmzrs:"RHMZ Republike Srpske",jadran:"Agencija za vodno područje Jadranskog mora"};
const GA=SNAP.gauges||[];

// ---- localisation ----------------------------------------------------------
// Bosnian counted strings need three forms [one, few, many]; English [one, other, other].
const I18N={
 bs:{title:"FloodWatch Bosna i Hercegovina",none:"Nema upozorenja",
  alerts:["općina pod upozorenjem","općine pod upozorenjem","općina pod upozorenjem"],
  sub:"Bosna i Hercegovina",upd:"ažurirano",stale:"podaci stariji od 9 h",
  d0:"Danas",d1:"Sutra",peak:"7 dana",rivers:"rijeke",model:"model",gauges:"Mjerenja",ok:"ok",
  warnHd:"Pod upozorenjem",nearHd:"Najbliže pragu pažnje",noWarn:"Nema upozorenja za odabrani dan.",
  watch:"Pažnja",warning:"Upozorenje",severe:"Opasnost",normal:"Normalno",
  now:"Sada",peakv:"Vrhunac",day:"Dan",flow:"Protok",ofWatch:"praga pažnje",
  near:"obližnja ćelija modela, izvan općine",river:"Rijeka",show:"Prikaži",gmaps:"Google Maps",
  noriver:"Nema značajnog vodotoka u modelu",forecast:"Prognoza",legend:"Legenda",layers:"Slojevi",
  lRiv:"Rijeke (prognoza)",lMuni:"Općine",lGa:"Mjerenja",hide:"Sakrij/prikaži sloj",
  legendTxt:"Nivo je prognoza protoka u ćeliji modela (~5 km) koja dostiže vrijednost koja se javlja jednom u 2, 5 ili 20 godina. Nije zvanično upozorenje.",
  docs:"Dokumentacija",src:"Prognoza protoka",map:"rijeke i granice",
  attrNote:"Model prognoze, nije zvanično upozorenje.",
  today:"danas",past:"prošlost",mid50:"srednjih 50% članova",minmax:"najbolji–najgori član",worst:"najgori član",
  wToday:"danas",wTomorrow:"sutra",wIn:"za {n} dana",
  sumExceed:"Prag pažnje se prekoračuje {d} ({w}); vrhunac {pd} je {p}% praga pažnje.",
  sumTop:"Najviši nivo: {l}.",
  sumWorst:"Glavna prognoza ne prelazi prag pažnje, ali najgori član skupa prognoza ga prelazi {d} ({w}), do {p}% praga.",
  sumNone:"Bez prekoračenja praga pažnje u 7 dana. Vrhunac glavne prognoze: {p}% praga.",
  sumNoneW:"Najgori član skupa: {w}%.",
  chartLegend:"Linija: glavna prognoza · tamno polje: srednjih 50% članova skupa · svijetlo: od najboljeg do najgoreg člana.",
  stripLegend:"Gore: glavna prognoza po danima · dolje: najgori član skupa. Klik bira dan.",
  fillNote:"Ovaj dio rijeke nema vlastitu ćeliju modela; prikazan je nivo najbliže tačke ({m}).",
  more:["još {n} rijeka u općini {m}","još {n} rijeke u općini {m}","još {n} rijeka u općini {m}"],
  coverage:"Prikazane su samo rijeke koje model prognoze razlikuje (~5 km). Manji vodotoci nisu pokriveni, a odsustvo upozorenja ne znači da rizika nema.",
  gsrc:"Izvor",gval:"Očitanje",gtime:"Vrijeme",gstale:"Podaci stariji od 6 h",gcls:"Zvanična klasa izvora",
  gnocls:"Granične vrijednosti nisu definisane",gnounit:"jedinica nije navedena u izvoru",gthr:"Pragovi odbrane (izvor)",
  gepoch:"vrijeme prema izvoru, vremenska zona nije potvrđena",gnone:"bez očitanja",ghist:"Očitanja koja smo zabilježili",
  gnote:"Podaci agencija su informativni i nisu zvanični. Prikazani su kako ih objavljuje izvor.",
  redovna_obrana:"redovna",vanredna_obrana:"vanredna",kontinuirana_obrana:"kontinuirana",loading:"Učitavanje karte…"},
 en:{title:"FloodWatch Bosnia and Herzegovina",none:"No alerts",
  alerts:["municipality on alert","municipalities on alert","municipalities on alert"],
  sub:"Bosnia and Herzegovina",upd:"updated",stale:"data older than 9 h",
  d0:"Today",d1:"Tomorrow",peak:"7 days",rivers:"rivers",model:"model",gauges:"Gauges",ok:"ok",
  warnHd:"On alert",nearHd:"Closest to the watch level",noWarn:"No alerts for the selected day.",
  watch:"Watch",warning:"Warning",severe:"Severe",normal:"Normal",
  now:"Now",peakv:"Peak",day:"Day",flow:"Discharge",ofWatch:"of the watch level",
  near:"nearby model cell, outside the municipality",river:"River",show:"Show",gmaps:"Google Maps",
  noriver:"No significant river in the model",forecast:"Forecast",legend:"Legend",layers:"Layers",
  lRiv:"Rivers (forecast)",lMuni:"Municipalities",lGa:"Gauges",hide:"Hide/show layer",
  legendTxt:"A level is a forecast: the flow in a ~5 km model cell reaches a value that occurs about once in 2, 5 or 20 years. It is not an official warning.",
  docs:"Documentation",src:"River-flow forecast",map:"rivers and boundaries",
  attrNote:"Model forecast, not an official warning.",
  today:"today",past:"past",mid50:"middle 50% of members",minmax:"best–worst member",worst:"worst member",
  wToday:"today",wTomorrow:"tomorrow",wIn:"in {n} days",
  sumExceed:"The watch level is exceeded on {d} ({w}); the peak on {pd} is {p}% of the watch level.",
  sumTop:"Highest level: {l}.",
  sumWorst:"The main forecast stays below the watch level, but the worst ensemble member exceeds it on {d} ({w}), up to {p}% of it.",
  sumNone:"No watch-level exceedance in 7 days. Main forecast peak: {p}% of the watch level.",
  sumNoneW:"Worst ensemble member: {w}%.",
  chartLegend:"Line: main forecast · dark band: middle 50% of ensemble members · light band: best to worst member.",
  stripLegend:"Top: main forecast per day · bottom: worst ensemble member. Click to pick a day.",
  fillNote:"This stretch has no model cell of its own; it shows the level of the nearest point ({m}).",
  more:["{n} more river in {m}","{n} more rivers in {m}","{n} more rivers in {m}"],
  coverage:"Only rivers the forecast model can resolve (~5 km) are shown. Smaller streams are not covered, and no alert does not mean there is no risk.",
  gsrc:"Source",gval:"Reading",gtime:"Time",gstale:"Data older than 6 h",gcls:"Source's official class",
  gnocls:"Thresholds not defined",gnounit:"unit not stated by the source",gthr:"Flood-defence thresholds (source)",
  gepoch:"time as published; time zone not confirmed",gnone:"no reading",ghist:"Readings we recorded",
  gnote:"Agency data is informative, not official. Shown as the source publishes it.",
  redovna_obrana:"regular",vanredna_obrana:"extraordinary",kontinuirana_obrana:"continuous",loading:"Loading map…"}};
let lang="bs";
try{ if(localStorage.getItem("fl_lang")==="en") lang="en"; }catch(e){}
const t=k=>I18N[lang][k]??k;
const plural=(n,f)=>{const a=n%10,b=n%100;return f[a===1&&b!==11?0:(a>=2&&a<=4&&(b<12||b>14))?1:2]};
const loc=()=>lang==="bs"?"bs":"en-GB";
const $=id=>document.getElementById(id);
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

// ---- levels per day ----------------------------------------------------------
function classify(q,th){
  if(q==null||!th) return "normal";
  let l="normal"; for(const k of ["watch","warning","severe"]) if(q>=th[k]) l=k; return l;
}
const rank=l=>LV.indexOf(l);
const DAYS=(()=>{const s=new Set();
  SNAP.municipalities.forEach(m=>m.rivers.forEach(r=>r.times.forEach(d=>{if(d>=SNAP.today)s.add(d)})));
  const a=[...s].sort().slice(0,8); return a.length?a:[SNAP.today];})();
const sel={day:0,peak:false};
function flowOn(r,day){const i=r.times.indexOf(day);return i<0?null:r.flows[i]}
const lvR=r=>sel.peak?r.level:classify(flowOn(r,DAYS[sel.day]),r.thresholds);
const lvM=m=>m.rivers.reduce((w,r)=>rank(lvR(r))>rank(w)?lvR(r):w,"normal");
const valR=r=>sel.peak?r.peak:flowOn(r,DAYS[sel.day]);
// Month and weekday names are written out: the browser's own Bosnian locale data is
// often missing (a headless Chrome printed "M10 24"), and FireWatch spells them too.
const MON={bs:["jan","feb","mar","apr","maj","jun","jul","aug","sep","okt","nov","dec"],
  en:["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]};
const MONL={bs:["januar","februar","mart","april","maj","juni","juli","august","septembar","oktobar","novembar","decembar"],
  en:["January","February","March","April","May","June","July","August","September","October","November","December"]};
const WD={bs:["ned","pon","uto","sri","čet","pet","sub"],en:["Sun","Mon","Tue","Wed","Thu","Fri","Sat"]};
function fmtDay(d,style){
  const [y,mo,da]=d.split("-").map(Number), wd=WD[lang][new Date(Date.UTC(y,mo-1,da)).getUTCDay()], bs=lang==="bs";
  if(style==="num") return `${da}.${mo}.`;
  if(style==="long") return bs?`${wd}, ${da}. ${MONL.bs[mo-1]}`:`${wd}, ${da} ${MONL.en[mo-1]}`;
  return bs?`${da}. ${MON.bs[mo-1]}`:`${da} ${MON.en[mo-1]}`;
}
function fmtTime(iso){
  const x=new Date(iso), p=n=>String(n).padStart(2,"0"), mo=x.getMonth(), da=x.getDate();
  return (lang==="bs"?`${da}. ${MON.bs[mo]}`:`${da} ${MON.en[mo]}`)+` ${p(x.getHours())}:${p(x.getMinutes())}`;
}

// ---- map ----------------------------------------------------------------------
const map=L.map("map",{zoomControl:true,attributionControl:true}).fitBounds([[42.5,15.7],[45.3,19.7]],{animate:false});
map.attributionControl.setPrefix('<a href="https://leafletjs.com" target="_blank" rel="noopener">Leaflet</a>');
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:18,
  attribution:'© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> · GloFAS via <a href="https://open-meteo.com/" target="_blank" rel="noopener">Open-Meteo.com</a> (CC BY 4.0)'}).addTo(map);
const polys=L.layerGroup().addTo(map), lines=L.layerGroup().addTo(map), dots=L.layerGroup().addTo(map), gl=L.layerGroup().addTo(map);
const show={riv:true,muni:true,ga:true};
map.on("popupopen",()=>closeOverlays("popup"));
let eyeOn=true;

// ---- charts -----------------------------------------------------------------------------
// One chart per river: the main forecast line, the ensemble spread behind it (middle 50% of
// the members dark, best-to-worst member light; forecast days only - the statistics are not
// available for the past), today's divider, and the thresholds that are within reach of the
// data. A calm river is scaled to its own data, with a note that its watch level is off the
// chart - scaling every chart up to its watch level made a river at 4% of it look flat.
function fmtQ(v){return v>=100?Math.round(v):v>=10?Math.round(v*10)/10:Math.round(v*100)/100}
function niceTicks(max,n){
  const raw=max/n, mag=Math.pow(10,Math.floor(Math.log10(raw))), f=raw/mag, step=(f<=1?1:f<=2?2:f<=5?5:10)*mag, o=[];
  for(let v=0;v<=max+1e-9;v+=step) o.push(v); return o;
}
function chart(r,W,H,full){
  const f=r.flows,T=r.times,n=f.length,th=r.thresholds,B=r.band; if(n<2) return "";
  const ti=Math.max(0,T.indexOf(SNAP.today)), di=T.indexOf(DAYS[sel.day]);
  let top=Math.max(...f.filter(v=>v!=null)); if(B) for(const v of B.max) if(v!=null&&v>top) top=v;
  const shown=[]; if(top>=0.35*th.watch) shown.push("watch");        // thresholds worth drawing:
  if(top>=0.8*th.watch) shown.push("warning"); if(top>=0.8*th.warning) shown.push("severe"); // only those within reach
  const ymax=Math.max(top,...shown.map(k=>th[k]))*1.08||1;
  const L=full?42:6, R=full?80:6, TP=full?12:4, BT=full?22:4;
  const x=i=>L+i*(W-L-R)/(n-1), y=v=>H-BT-(H-TP-BT)*v/ymax;
  const col=COL[r.level];
  let g=`<svg class="fchart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(t("flow"))}">`;
  if(full) for(const v of niceTicks(ymax,4)){
    g+=`<line x1="${L}" x2="${W-R}" y1="${y(v)}" y2="${y(v)}" stroke="#28313d"/><text x="${L-5}" y="${y(v)+3}" text-anchor="end" fill="#8b98a5" font-size="9.5">${fmtQ(v)}</text>`;
  }
  if(B){ // spread, drawn only over forecast days
    const idx=[...Array(n).keys()].filter(i=>i>=ti&&B.max[i]!=null&&B.min[i]!=null);
    const poly=(hi,lo)=>idx.map(i=>x(i)+","+y(B[hi][i])).join(" ")+" "+[...idx].reverse().map(i=>x(i)+","+y(B[lo][i])).join(" ");
    if(idx.length>1){ g+=`<polygon points="${poly("max","min")}" fill="${col}" opacity=".16"/><polygon points="${poly("p75","p25")}" fill="${col}" opacity=".3"/>`; }
  }
  for(const k of shown) g+=`<line x1="${L}" x2="${W-R}" y1="${y(th[k])}" y2="${y(th[k])}" stroke="${COL[k]}" stroke-dasharray="4 3" opacity=".85"/>`+
    (full?`<text x="${W-R+4}" y="${y(th[k])+3}" fill="${COL[k]}" font-size="9.5">${esc(t(k))} ${fmtQ(th[k])}</text>`:"");
  if(full&&!shown.includes("watch")) g+=`<text x="${W-R}" y="${TP+2}" text-anchor="end" fill="${COL.watch}" font-size="9.5">▲ ${esc(t("watch"))}: ${fmtQ(th.watch)} m³/s</text>`;
  const pt=a=>a.map((v,i)=>v==null?null:x(i)+","+y(v)).filter(Boolean).join(" ");
  if(ti>0) g+=`<polyline fill="none" stroke="#8b98a5" stroke-width="1.6" opacity=".7" points="${pt(f.slice(0,ti+1))}"/>`;
  g+=`<polyline fill="none" stroke="${col}" stroke-width="2.4" stroke-linejoin="round" points="${f.map((v,i)=>i>=ti&&v!=null?x(i)+","+y(v):null).filter(Boolean).join(" ")}"/>`;
  g+=`<line x1="${x(ti)}" x2="${x(ti)}" y1="${TP}" y2="${H-BT}" stroke="#8b98a5" stroke-dasharray="2 3" opacity=".6"/>`+(full?`<text x="${x(ti)+3}" y="${H-BT-3}" fill="#8b98a5" font-size="9">${esc(t("today"))}</text>`:"");
  if(di>=0&&f[di]!=null) g+=`<line x1="${x(di)}" x2="${x(di)}" y1="${TP}" y2="${H-BT}" stroke="#e6edf3" opacity=".35"/><circle cx="${x(di)}" cy="${y(f[di])}" r="3.6" fill="${col}" stroke="#0b0e12" stroke-width="1.2"/>`;
  if(full){
    T.forEach((d,i)=>{ if(i%2===0) g+=`<text x="${x(i)}" y="${H-7}" text-anchor="middle" fill="${i>=ti?"#aab6c2":"#6b7785"}" font-size="9">${fmtDay(d,"num")}</text>`});
    const w=(W-L-R)/(n-1);
    T.forEach((d,i)=>{ if(f[i]==null) return;
      const parts=[fmtDay(d,"long")+(i<ti?" · "+t("past"):""),`${t("flow")}: ${fmtQ(f[i])} m³/s`];
      if(B&&i>=ti&&B.max[i]!=null) parts.push(`${t("mid50")}: ${fmtQ(B.p25[i])}–${fmtQ(B.p75[i])}`,`${t("minmax")}: ${fmtQ(B.min[i])}–${fmtQ(B.max[i])}`);
      parts.push(`${Math.round(100*f[i]/th.watch)}% ${t("ofWatch")}`);
      g+=`<rect class="hit" x="${x(i)-w/2}" y="0" width="${w}" height="${H}" fill="transparent" data-tip="${esc(parts.join("||"))}"/>`;
    });
  }
  return g+"</svg>";
}
const dayWord=i=>i<=0?t("wToday"):i===1?t("wTomorrow"):t("wIn").replace("{n}",i);
function firstAt(a,thr,from){for(let i=from;i<a.length;i++) if(a[i]!=null&&a[i]>=thr) return i; return -1}
// One sentence that answers "should I worry, and when" - most people will not read a curve.
function summary(r){
  const th=r.thresholds,B=r.band,ti=Math.max(0,r.times.indexOf(SNAP.today)),pct=v=>Math.round(100*v/th.watch);
  const c=firstAt(r.flows,th.watch,ti), w=B?firstAt(B.max,th.watch,ti):-1;
  const wmax=B?Math.max(...B.max.filter(v=>v!=null)):null;
  if(c>=0){
    const hi=r.level==="normal"||r.level==="watch"?"":" "+t("sumTop").replace("{l}",t(r.level));
    return t("sumExceed").replace("{d}",fmtDay(r.times[c])).replace("{w}",dayWord(c-ti)).replace("{pd}",fmtDay(r.peak_day)).replace("{p}",pct(r.peak))+hi;
  }
  if(w>=0) return t("sumWorst").replace("{d}",fmtDay(r.times[w])).replace("{w}",dayWord(w-ti)).replace("{p}",pct(wmax));
  return t("sumNone").replace("{p}",pct(r.peak))+(B&&wmax!=null?" "+t("sumNoneW").replace("{w}",pct(wmax)):"");
}
// A strip of one cell per forecast day: top = main forecast's level, thin bar below = worst
// ensemble member's level. Readable at a glance, and the same for all 232 rivers.
function strip(r,legend){
  const cell=(d,i)=>{
    const k=r.times.indexOf(d), q=flowOn(r,d), l=classify(q,r.thresholds), mx=r.band&&k>=0?r.band.max[k]:null;
    const lw=mx==null?l:(rank(classify(mx,r.thresholds))>rank(l)?classify(mx,r.thresholds):l);
    return `<button type="button" class="cell${!sel.peak&&sel.day===i?" on":""}" data-day="${i}" title="${esc(fmtDay(d,"long")+": "+t(l)+(lw!==l?" ("+t("worst")+": "+t(lw)+")":""))}"><i style="background:${COL[l]}"></i><b style="background:${COL[lw]}"></b><span>${fmtDay(d,"num")}</span></button>`;
  };
  return `<div class="strip">${DAYS.map(cell).join("")}</div>`+(legend?`<div class="mut" style="font-size:11px;margin-top:3px">${t("stripLegend")}</div>`:"");
}
function riverBlock(r){
  const l=lvR(r), v=valR(r);
  return `<div class="rv"><b>${esc(r.river||"")}</b> <span style="color:${COL[l]}">● ${t(l)}</span>${r.near?` <span class="mut">(${t("near")})</span>`:""}
   <div class="mut">${t("day")}: ${v==null?"–":v+" m³/s"} · ${t("peakv")}: ${r.peak} m³/s (${fmtDay(r.peak_day)})</div>
   <div style="margin-top:6px;font-size:12.5px">${esc(summary(r))}</div>
   ${chart(r,340,170,true)}<div class="mut" style="font-size:11px">${t("chartLegend")}</div>${strip(r,true)}</div>`;
}
// A river dot, line or card opens just that river, with a link to the rest; the
// municipality area opens the full list (the reader asked about the whole place).
// Only one overlay at a time: opening any of them closes the others. Without this a municipality
// dialog, a gauge popup, the layers menu and the legend could all pile up on top of each other.
function closeOverlays(except){
  if(except!=="muni") $("muniinfo").classList.remove("show");
  if(except!=="popup") map.closePopup();
  if(except!=="layers") $("layerspanel").classList.remove("open");
  if(except!=="legend"){ const lg=document.querySelector(".legend"); if(lg) lg.classList.remove("open"); }
  if(typeof tip!=="undefined") tip.style.display="none";
}
let cur=null;
function openMuni(m,at,r,note){
  closeOverlays("muni");
  cur={m,r,note};
  if(at) map.setView(at,Math.max(map.getZoom(),10),{animate:false});
  const body=$("muniinfo-body");
  const render=all=>{
    const rs=r?(all?[r,...m.rivers.filter(x=>x!==r)]:[r]):m.rivers;
    let h=`<h2 style="margin:0 0 4px;font-size:15px">${esc(m.name)}</h2>`;
    h+=rs.length?rs.map(riverBlock).join(""):`<div class="mut">${t("noriver")}</div>`;
    if(note&&!all) h+=`<div class="mut" style="margin-top:8px">${esc(note)}</div>`;
    if(r&&!all&&m.rivers.length>1){
      const n=m.rivers.length-1;
      h+=`<a href="#" class="more" data-more="1">${plural(n,t("more")).replace("{n}",n).replace("{m}",esc(m.name))}</a>`;
    }
    if(rs.length) h+=`<div class="mut" style="margin-top:8px">${t("attrNote")}</div>`;
    body.innerHTML=h+`<div class="mut" style="margin-top:6px">${t("coverage")}</div>`;
    const more=body.querySelector("[data-more]");
    if(more) more.onclick=e=>{e.preventDefault();render(true)};
  };
  render(false);
  $("muniinfo").classList.add("show");
}
function atOf(m,r){const g=(RIV[m.id]||[]).find(x=>x.name===r.river);return g?[g.mlat,g.mlon]:[r.lat,r.lon]}

function drawMap(){
  polys.clearLayers(); lines.clearLayers(); dots.clearLayers();
  const seen={};
  for(const m of SNAP.municipalities){
    const lm=lvM(m), up=lm!=="normal";
    if(BOUNDS[m.id]&&show.muni)
      L.polygon(BOUNDS[m.id],{color:COL[lm],weight:up?2:.8,opacity:up?.95:.45,fillColor:COL[lm],fillOpacity:up?.36:.03})
        .addTo(polys).on("click",()=>openMuni(m));
    if(!show.riv) continue;
    for(const r of m.rivers){
      const l=lvR(r), ru=l!=="normal", g=(RIV[m.id]||[]).find(x=>x.name===r.river);
      if(g&&g.lines.length) L.polyline(g.lines,{color:COL[l],weight:ru?9:4,opacity:ru?.95:.9,lineCap:"round"}).addTo(lines).on("click",()=>openMuni(m,null,r));
      const at=atOf(m,r), key=at+","+l; if(seen[key]) continue; seen[key]=1;
      L.circleMarker(at,{radius:ru?13.5:6,color:"#0b0e12",weight:2,fillColor:COL[l],fillOpacity:.95}).addTo(dots).on("click",()=>openMuni(m,null,r));
    }
  }
  // Stretches of a river inside municipalities that have no point for it: drawn so the river is
  // continuous, in the level colour of the nearest stretch of the same river.
  if(show.riv) for(const [name,list] of Object.entries(FILL)) for(const f of list){
    const m=SNAP.municipalities.find(x=>x.id===f.ref), r=m&&m.rivers.find(x=>x.river===name); if(!r) continue;
    const l=lvR(r), ru=l!=="normal";
    L.polyline(f.lines,{color:COL[l],weight:ru?9:4,opacity:ru?.95:.9,lineCap:"round"}).addTo(lines)
      .on("click",()=>openMuni(m,null,r,t("fillNote").replace("{m}",m.name)));
  }
  if(!eyeOn){ for(const g of [polys,lines,dots,gl]) map.removeLayer(g); } else { for(const g of [polys,lines,dots]) g.addTo(map); if(show.ga) gl.addTo(map); }
}

// ---- gauges -------------------------------------------------------------------
function gspark(h,col){
  if(!h||h.length<2) return "";
  const W=210,H=46,v=h.map(p=>p[1]),lo=Math.min(...v),hi=Math.max(...v),r=(hi-lo)||1;
  const x=i=>4+i*(W-8)/(h.length-1), y=a=>H-4-(H-8)*(a-lo)/r;
  return `<svg width="${W}" height="${H}" role="img" aria-label="${t("ghist")}"><polyline fill="none" stroke="${col}" stroke-width="2" points="${v.map((a,i)=>x(i)+","+y(a)).join(" ")}"/></svg>
   <div class="mut">${t("ghist")}: ${h.length}× · ${lo} – ${hi}</div>`;
}
function gaugePopup(g){
  const unit=g.unit||"", stale=g.time&&(Date.now()-Date.parse(g.time))>6*3600e3;
  const val=g.value==null?t("gnone"):`${g.value} ${esc(unit)}${g.unit?"":` <span class="mut">(${t("gnounit")})</span>`}`;
  const cls=g.source==="sava"?`<div>${t("gcls")}: <b>${g.class||"–"}</b>${g.class?"":` <span class="mut">(${t("gnocls")})</span>`}</div>`:"";
  const thr=g.thresholds?`<div class="mut">${t("gthr")}: ${Object.entries(g.thresholds).map(([k,v])=>t(k)+" "+v).join(" · ")}</div>`:"";
  const when=g.time?`${g.time.replace("T"," ").slice(0,16)}${stale?` · <b>${t("gstale")}</b>`:""}`
    :g.time_raw_epoch?`${new Date(g.time_raw_epoch*1000).toISOString().replace("T"," ").slice(0,16)} <span class="mut">(${t("gepoch")})</span>`:"–";
  return `<div><b>${esc(g.name)}</b>${g.river?` <span class="mut">· ${esc(g.river)}</span>`:""}
   <div>${t("gval")}: <b>${val}</b></div>${cls}${thr}<div class="mut">${t("gtime")}: ${when}</div>${gspark(g.history,g.class?GCOL[g.class]:"#8b98a5")}
   <div class="mut">${t("gsrc")}: ${GSRC[g.source]}</div><div class="mut" style="margin-top:4px">${t("gnote")}</div></div>`;
}
function drawGauges(){
  gl.clearLayers();
  for(const g of GA)
    L.marker([g.lat,g.lon],{icon:L.divIcon({className:"",html:`<div class="gsq" style="background:${g.value==null?"transparent":(g.class?GCOL[g.class]:"#c7d0d9")}"></div>`,iconSize:[18,18]})})
      .addTo(gl).bindPopup(()=>gaugePopup(g),{autoPan:false,maxHeight:300});
}

// ---- side panel -----------------------------------------------------------------
function counts(){ // municipalities at watch or above, per view
  const save={...sel}, out=[];
  for(let i=0;i<Math.min(4,DAYS.length);i++){ sel.day=i; sel.peak=false; out.push(SNAP.municipalities.filter(m=>lvM(m)!=="normal").length); }
  sel.day=0; sel.peak=true; const pk=SNAP.municipalities.filter(m=>lvM(m)!=="normal").length;
  Object.assign(sel,save); return {days:out,peak:pk};
}
function renderHeader(){
  const c=counts(), onAlert=SNAP.municipalities.filter(m=>lvM(m)!=="normal");
  const worst=onAlert.reduce((w,m)=>rank(lvM(m))>rank(w)?lvM(m):w,"normal");
  $("hdot").style.background=worst==="normal"?"#3fb950":COL[worst];
  const n=onAlert.length;
  $("htitle").textContent=n?`${n} ${plural(n,t("alerts"))}`:t("none");
  const when=fmtTime(SNAP.generated_at);
  const old=(Date.now()-Date.parse(SNAP.generated_at))>9*3600e3;
  $("hsub").innerHTML=`${t("sub")} · ${t("upd")} ${when}${old?` · <b style="color:#ff6b6b">⚠ ${t("stale")}</b>`:""}`;
  const labels=DAYS.slice(0,4).map((d,i)=>i===0?t("d0"):i===1?t("d1"):fmtDay(d));
  const btns=labels.map((l,i)=>`<button data-i="${i}" class="${!sel.peak&&sel.day===i?"on":""}">${l}<b>(${c.days[i]})</b></button>`);
  btns.push(`<button data-p="1" class="${sel.peak?"on":""}">${t("peak")}<b>(${c.peak})</b></button>`);
  $("hrange").innerHTML=btns.join("");
  const nr=SNAP.municipalities.reduce((a,m)=>a+m.rivers.length,0);
  $("hchips").innerHTML=`<span class="chip">${t("model")} <b class="ok">${t("ok")}</b></span><span class="chip">${t("rivers")} <b>${nr}</b></span>`+(GA.length?`<span class="chip">${t("gauges")} <b>${GA.length}</b></span>`:"");
  $("drawer-badge").textContent=n?String(n):"";
  const pub=location.protocol==="https:";
  $("chbtn").textContent=pub?t("docs"):""; if(pub) $("chbtn").href="docs/floodwatch-documentation.html";
  $("foot").innerHTML=`${t("src")}: GloFAS · <a class="foot-link" href="https://open-meteo.com/" target="_blank" rel="noopener">Open-Meteo.com</a> (CC BY 4.0) &nbsp;|&nbsp; ${t("map")}: OSM`+(pub?` &nbsp;|&nbsp; <a class="foot-link" href="docs/floodwatch-documentation.html">${t("docs")}</a>`:"");
}
function card(m,r){
  const l=r?lvR(r):lvM(m), at=r?atOf(m,r):null, v=r?valR(r):null;
  const ratio=r&&v!=null?Math.round(100*v/r.thresholds.watch):null;
  return `<div class="ev" style="border-left-color:${COL[l]}" data-m="${m.id}" data-r="${r?esc(r.river):""}">
    <h2>${esc(m.name)}<span class="sev lv-${l}">${t(l)}</span></h2>
    <div class="meta">${r?`<span>${t("river")}</span><span>${esc(r.river||"–")}${r.near?` <i style="color:var(--dim)">(≈)</i>`:""}</span>
      <span>${t("day")}</span><span>${v==null?"–":v+" m³/s"}</span><span>${t("peakv")}</span><span>${r.peak} m³/s · ${fmtDay(r.peak_day)}</span>`:""}</div>
    ${ratio!=null?`<div class="ratio" title="${ratio}% ${t("ofWatch")}"><span style="width:${Math.min(100,ratio)}%;background:${COL[l==="normal"?"watch":l]}"></span></div>
      <div class="meta" style="margin-top:4px"><span></span><span>${ratio}% ${t("ofWatch")}</span></div>`:""}
    ${r?chart(r,300,60,false)+`<div class="mut" style="margin-top:6px;font-size:11.5px">${esc(summary(r))}</div>`+strip(r):""}
    ${at?`<div class="acts"><button data-act="show">${t("show")}</button>
      <a href="https://www.google.com/maps/@?api=1&map_action=map&center=${at[0]},${at[1]}&zoom=13" target="_blank" rel="noopener">${t("gmaps")}</a></div>`:""}</div>`;
}
function renderList(){
  const on=SNAP.municipalities.filter(m=>lvM(m)!=="normal").sort((a,b)=>rank(lvM(b))-rank(lvM(a)));
  let h="";
  if(on.length){
    h+=`<div class="sechd">${t("warnHd")}</div>`;
    for(const m of on){ const rs=m.rivers.filter(r=>lvR(r)!=="normal").sort((a,b)=>rank(lvR(b))-rank(lvR(a))); h+=card(m,rs[0]); }
  } else {
    h+=`<div class="empty"><div class="big">💧</div>${t("noWarn")}<div class="mut" style="margin-top:10px;font-size:11.5px">${t("coverage")}</div></div>`;
    const all=[]; SNAP.municipalities.forEach(m=>m.rivers.forEach(r=>{const v=valR(r); if(v!=null) all.push({m,r,q:v/r.thresholds.watch})}));
    all.sort((a,b)=>b.q-a.q);
    h+=`<div class="sechd">${t("nearHd")}</div>`+all.slice(0,6).map(x=>card(x.m,x.r)).join("");
  }
  $("list").innerHTML=h;
}
$("list").addEventListener("click",e=>{
  const c=e.target.closest(".ev"); if(!c||e.target.closest("a")) return;
  const m=SNAP.municipalities.find(x=>x.id===c.dataset.m); if(!m) return;
  const r=m.rivers.find(x=>(x.river||"")===c.dataset.r)||m.rivers[0];
  openMuni(m,r?atOf(m,r):null,r); drawer(false);
});

// ---- bottom bar: forecast days -------------------------------------------------------
function renderDays(){
  $("days").innerHTML=DAYS.map((d,i)=>{
    const worst=SNAP.municipalities.reduce((w,m)=>m.rivers.reduce((a,r)=>{const l=classify(flowOn(r,d),r.thresholds);return rank(l)>rank(a)?l:a},w),"normal");
    return `<button data-i="${i}" class="${!sel.peak&&sel.day===i?"on":""}">${fmtDay(d,"num")}<b>${i===0?t("d0"):"+"+i}</b><i style="background:${COL[worst]}"></i></button>`;
  }).join("");
  $("tlabel").textContent=sel.peak?t("peak"):`${fmtDay(DAYS[sel.day],"long")}`;
}
function setView(day,peak){ sel.day=day; sel.peak=!!peak; refresh(); }
$("hrange").addEventListener("click",e=>{const b=e.target.closest("button"); if(!b) return; b.dataset.p?setView(0,true):setView(+b.dataset.i,false)});
$("days").addEventListener("click",e=>{const b=e.target.closest("button"); if(b) setView(+b.dataset.i,false)});
let timer=null, speed=1;
function stopPlay(){ if(timer){clearInterval(timer);timer=null} $("play").innerHTML="&#9654;" }
function startPlay(){
  stopPlay(); $("play").innerHTML="&#10074;&#10074;"; if(sel.peak||sel.day>=DAYS.length-1) setView(0,false);
  timer=setInterval(()=>{ if(sel.day>=DAYS.length-1){stopPlay();return} setView(sel.day+1,false) },1400/speed);
}
$("play").onclick=()=>timer?stopPlay():startPlay();
$("speed").onclick=()=>{speed=speed===1?2:speed===2?4:1;$("speed").innerHTML=speed+"&times;"; if(timer) startPlay()};

// ---- chrome: drawer, language, layers, eye, legend ----------------------------------------
function drawer(open){if(open) closeOverlays();document.body.classList.toggle("drawer-open",open);$("side").classList.toggle("open",open);
  $("backdrop").classList.toggle("on",open);$("drawer-btn").setAttribute("aria-expanded",open)}
$("drawer-btn").onclick=()=>drawer(true); $("drawer-close").onclick=()=>drawer(false); $("backdrop").onclick=()=>drawer(false);
$("muniinfo").querySelector(".miclose").onclick=()=>$("muniinfo").classList.remove("show");
$("langsw").addEventListener("click",e=>{const b=e.target.closest("button"); if(!b) return; lang=b.dataset.l; try{localStorage.setItem("fl_lang",lang)}catch(x){}; refresh(true)});
function renderLayers(){
  $("layersbtn").textContent=t("layers");
  $("layerspanel").innerHTML=`<label><input type="checkbox" data-k="riv" ${show.riv?"checked":""}> ${t("lRiv")}</label>
    <label><input type="checkbox" data-k="muni" ${show.muni?"checked":""}> ${t("lMuni")}</label>`+
    (GA.length?`<label><input type="checkbox" data-k="ga" ${show.ga?"checked":""}> ${t("lGa")} (${GA.length})</label>`:"");
}
$("layersbtn").onclick=()=>{const o=!$("layerspanel").classList.contains("open"); if(o) closeOverlays("layers"); $("layerspanel").classList.toggle("open",o)};
$("layerspanel").addEventListener("change",e=>{const k=e.target.dataset.k; if(!k) return; show[k]=e.target.checked;
  if(k==="ga"){e.target.checked?gl.addTo(map):map.removeLayer(gl)} else drawMap()});
const tools=L.control({position:"topleft"});
tools.onAdd=()=>{const d=L.DomUtil.create("div","");
  d.innerHTML=`<div class="tool" id="eyebtn" role="button" tabindex="0" title="${t("hide")}" aria-label="${t("hide")}">&#128065;</div>`;
  L.DomEvent.disableClickPropagation(d);
  d.querySelector("#eyebtn").onclick=ev=>{eyeOn=!eyeOn;ev.currentTarget.classList.toggle("off",!eyeOn);drawMap()}; return d};
tools.addTo(map);
const legend=L.control({position:"bottomright"});
legend.onAdd=()=>{const d=L.DomUtil.create("div","legend"); L.DomEvent.disableClickPropagation(d);
  d.innerHTML=`<div class="legend-body" id="lgbody"></div><button class="legend-toggle" id="lgbtn" type="button"></button>`;
  d.querySelector("#lgbtn").onclick=()=>{const o=!d.classList.contains("open"); if(o) closeOverlays("legend"); d.classList.toggle("open",o)}; return d};
legend.addTo(map);
function renderLegend(){
  $("lgbtn").textContent="▥ "+t("legend");
  $("lgbody").innerHTML=["normal","watch","warning","severe"].map(k=>`<div><i style="background:${COL[k]}"></i>${t(k)}</div>`).join("")+
    `<div style="margin-top:6px">${t("legendTxt")}</div><div style="margin-top:6px"><b>${t("coverage")}</b></div>`+
    (GA.length?`<div style="margin-top:8px"><i class="sq" style="background:#c7d0d9"></i>${t("lGa")}: ${["N","P","R","V","Z"].map(k=>`<i class="sq" style="background:${GCOL[k]};margin-left:6px"></i>${k}`).join("")}</div>`:"");
}

// ---- one refresh ----------------------------------------------------------------------
function refresh(full){
  document.documentElement.lang=lang; document.title=t("title");
  $("drawer-label").textContent=t("rivers").replace(/^./,c=>c.toUpperCase());
  $("ldsub").textContent=t("loading");
  document.querySelectorAll("#langsw button").forEach(b=>b.classList.toggle("on",b.dataset.l===lang));
  renderHeader(); renderList(); renderDays(); renderLayers(); renderLegend(); drawMap(); if(full) drawGauges();
  if(cur&&$("muniinfo").classList.contains("show")) openMuni(cur.m,null,cur.r,cur.note);
}
const tip=document.createElement("div"); tip.id="tip"; document.body.appendChild(tip);
function showTip(e){
  const h=e.target.closest&&e.target.closest(".hit");
  if(!h){tip.style.display="none";return}
  tip.innerHTML=h.dataset.tip.split("||").map(esc).join("<br>"); tip.style.display="block";
  tip.style.left=Math.max(8,Math.min(e.clientX+12,innerWidth-tip.offsetWidth-8))+"px";
  tip.style.top=Math.max(8,e.clientY-tip.offsetHeight-14)+"px";
}
document.addEventListener("pointermove",showTip); document.addEventListener("pointerdown",showTip);
document.addEventListener("click",e=>{const c=e.target.closest&&e.target.closest(".cell"); if(!c) return; e.stopPropagation(); setView(+c.dataset.day,false)},true);
function setVh(){document.documentElement.style.setProperty("--appvh",innerHeight+"px")}
addEventListener("resize",setVh); setVh();
refresh(true);
setTimeout(()=>$("loading").classList.add("hide"),450);
</script></body></html>"""


def render(snapshot: dict) -> str:
    bounds = json.loads((config.DATA_DIR / "boundaries-simple.json").read_text())
    rivers: dict[str, list] = {}
    if config.POINTS_FILE.exists():
        for p in json.loads(config.POINTS_FILE.read_text()):
            if p.get("mlat") is not None:
                rivers.setdefault(p["id"], []).append(
                    {"name": p["river_name"], "mlat": p["mlat"], "mlon": p["mlon"], "lines": p["lines"]})
    fill_file = config.DATA_DIR / "river_fill.json"
    fill = json.loads(fill_file.read_text()) if fill_file.exists() else {}
    page = TEMPLATE.replace("__CSS__", CSS + EXTRA_CSS)
    return (page.replace("__SNAPSHOT__", json.dumps(snapshot, ensure_ascii=False))
                .replace("__BOUNDS__", json.dumps(bounds, separators=(",", ":")))
                .replace("__RIVERS__", json.dumps(rivers, ensure_ascii=False, separators=(",", ":")))
                .replace("__FILL__", json.dumps(fill, ensure_ascii=False, separators=(",", ":"))))
