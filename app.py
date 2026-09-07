# -*- coding: utf-8 -*-
"""LineBuilder web app: build a cleanroom process line with per-step dropdowns,
compute its EF 3.1 climate-change footprint. Run:  python app.py  -> http://127.0.0.1:5000"""
from flask import Flask, request, jsonify, Response, send_file
import os, tempfile
import linebuilder_core as core

app = Flask(__name__)

PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><title>LineBuilder — GWP</title>
<style>
 :root{
   --ink:#243043; --ink2:#5b6880; --line:#e3e8f0; --bg:#f7f9fc; --card:#fff;
   --accent:#3563b0; --accent-soft:#eef3fb; --ok:#2e7d5b; --warn:#b3261e;
 }
 *{box-sizing:border-box}
 body{font-family:'Segoe UI',system-ui,Arial,sans-serif;margin:0;background:var(--bg);
      color:var(--ink);font-size:14px;line-height:1.5;-webkit-font-smoothing:antialiased}
 header{background:var(--card);border-bottom:1px solid var(--line);padding:18px 28px}
 header h1{margin:0;font-size:20px;font-weight:650;color:var(--accent);letter-spacing:-.2px}
 header p{margin:5px 0 0;font-size:13px;color:var(--ink2);max-width:70ch}
 .wrap{max-width:1120px;margin:22px auto 60px;padding:0 24px}

 /* ---------- setup panel ---------- */
 .setup{background:var(--card);border:1px solid var(--line);border-radius:12px;
        padding:6px 20px 16px;margin-bottom:20px}
 .grp{display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:12px 0}
 .grp + .grp{border-top:1px solid var(--line)}
 .grp > .gl{font-size:11px;font-weight:700;letter-spacing:.7px;text-transform:uppercase;
            color:var(--ink2);min-width:120px}
 .grp label{display:inline-flex;align-items:center;gap:6px;font-size:13px;color:var(--ink2)}

 /* ---------- controls ---------- */
 select,input{font-size:13.5px;padding:7px 10px;border:1px solid #ccd5e3;border-radius:8px;
              background:var(--card);color:var(--ink);font-family:inherit}
 select:focus,input:focus{outline:2px solid var(--accent-soft);border-color:var(--accent)}
 input[type=number]{width:88px}
 select.stype{font-weight:600;min-width:300px;font-size:14px}
 button{cursor:pointer;border:none;border-radius:8px;padding:8px 14px;font-size:13.5px;
        font-family:inherit;transition:filter .12s}
 button:hover{filter:brightness(.96)}
 .icon{background:#eff3f9;color:#3a465c;padding:7px 11px;font-weight:500}
 .add{background:var(--accent-soft);color:var(--accent);font-weight:600;
      border:1.5px dashed #a9c0e4;width:100%;padding:13px;font-size:14px}
 .go{background:var(--accent);color:#fff;font-weight:650;padding:12px 26px;font-size:15px}

 /* ---------- step cards ---------- */
 .step{background:var(--card);border:1px solid var(--line);border-radius:12px;
       padding:16px 18px;margin-bottom:12px}
 .step-head{display:flex;align-items:center;gap:12px}
 .badge{background:var(--accent-soft);color:var(--accent);font-weight:700;border-radius:8px;
        padding:5px 11px;font-size:13px;min-width:30px;text-align:center}
 .mv{margin-left:auto;display:flex;gap:6px}
 .stepnote{font-size:13px;color:var(--ink2);margin:10px 0 0 42px;padding:9px 13px;
           background:#f8fafd;border-left:3px solid #cddbf0;border-radius:0 6px 6px 0;max-width:85ch}
 .params{display:grid;grid-template-columns:repeat(auto-fill,minmax(172px,1fr));
         gap:14px 18px;margin:14px 0 0 42px}
 .p{display:flex;flex-direction:column;gap:4px;min-width:0}
 .p label{font-size:12px;color:var(--ink2);font-weight:500;white-space:nowrap;
          overflow:hidden;text-overflow:ellipsis}
 .p label[title]{cursor:help;border-bottom:1px dotted #b8c4d6;align-self:flex-start}
 .p input,.p select{width:100%}
 .adv{grid-column:1/-1;margin-top:2px}
 .adv>summary{font-size:12px;color:var(--ink2);cursor:pointer;list-style:none;
              display:inline-flex;align-items:center;gap:5px;user-select:none;
              padding:3px 0;border-bottom:1px dotted #b8c4d6}
 .adv>summary::before{content:'\25B8';font-size:10px;transition:transform .15s}
 .adv[open]>summary::before{transform:rotate(90deg)}
 .advgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(172px,1fr));
          gap:14px 18px;margin-top:12px}

 /* ---------- results ---------- */
 .res{background:var(--card);border:1px solid var(--line);border-radius:12px;
      padding:22px 24px;margin-top:20px}
 .total{font-size:34px;font-weight:750;color:var(--accent);letter-spacing:-.5px}
 table{width:100%;border-collapse:collapse;margin-top:16px;font-size:13.5px}
 th{text-align:left;font-size:11px;letter-spacing:.6px;text-transform:uppercase;
    color:var(--ink2);padding:0 8px 8px;border-bottom:1px solid var(--line);font-weight:700}
 td{padding:9px 8px;border-bottom:1px solid #f0f3f8;vertical-align:middle}
 tr:last-child td{border-bottom:none}
 .bar{height:9px;background:linear-gradient(90deg,#6f9fdb,#3563b0);border-radius:99px;min-width:3px}
 .num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
 .muted{color:var(--ink2);font-size:13px}
 .err{color:var(--warn);font-weight:600}
</style></head><body>
<header><h1>LineBuilder — cleanroom process line → carbon footprint</h1>
<p>Load a standard flow or add steps one by one. Each step's parameters appear automatically —
hover a parameter name to see what it means. Results use EF 3.1 climate change (GWP100).</p></header>
<div class="wrap">
  <div class="setup">
    <div class="grp">
      <span class="gl">Substrate</span>
      <label><input type="checkbox" id="incSub" style="width:auto"> include as a step</label>
      <select id="subFormat" title="A real, purchasable wafer: material + SEMI-standard diameter + its coupled thickness. Impossible sizes are not listed"></select>
      <label>wafers <input type="number" id="nWaf" value="1" min="1" style="width:70px"></label>
    </div>
    <div class="grp">
      <span class="gl">Electricity</span>
      <select id="gridSel" title="Grid choice is the single biggest lever in a cleanroom line">
        <option value="CH" selected>CH — Switzerland</option><option value="DE">DE — Germany</option>
        <option value="FR">FR — France</option><option value="IT">IT — Italy</option>
        <option value="NL">NL — Netherlands</option><option value="RER">RER — Europe</option>
        <option value="JP">JP — Japan</option><option value="KR">KR — Korea</option>
        <option value="TW">TW — Taiwan</option><option value="CN">CN — China</option>
        <option value="US">US — United States</option>
      </select>
      <select id="voltSel" title="Medium = standard cleanroom feed. High = fab fed directly from the HV grid (e.g. PSI), ~12% lower">
        <option value="MV" selected>medium voltage</option>
        <option value="HV">high voltage</option>
      </select>
    </div>
    <div class="grp">
      <span class="gl">Standard flow</span>
      <select id="flowSel" style="min-width:400px"><option value="">— pick a ready-made process sequence —</option></select>
      <button class="icon" onclick="loadFlow(false)">Append</button>
      <button class="icon" onclick="loadFlow(true)">Replace all</button>
    </div>
  </div>
  <div id="steps"></div>
  <button class="add" onclick="addStep()">+ Add step</button>
  <div style="margin-top:14px"><button class="go" onclick="compute()">Compute GWP ▶</button>
     <button class="icon" style="padding:11px 16px;font-size:14px" onclick="download_db()">⤓ Download database (Excel)</button>
     <span id="status" class="muted"></span></div>
  <div id="result"></div>
</div>
<script>
let SCHEMA=null, byId={};
async function init(){
  SCHEMA=await (await fetch('/schema')).json();
  SCHEMA.steps.forEach(s=>byId[s.id]=s);
  const fs=document.getElementById('flowSel');
  (SCHEMA.flows||[]).forEach(f=>{
    const o=document.createElement('option'); o.value=f.id;
    o.textContent=f.label; o.title=f.about||''; fs.appendChild(o);
  });
  // wafer-format dropdown, grouped by material (only REAL formats -> no impossible sizes)
  const sf=document.getElementById('subFormat'); const fmts=SCHEMA.substrate_formats||{};
  const byMat={}; Object.keys(fmts).forEach(k=>{(byMat[fmts[k].mat]=byMat[fmts[k].mat]||[]).push(k);});
  Object.keys(byMat).forEach(mat=>{
    const og=document.createElement('optgroup'); og.label=mat;
    byMat[mat].forEach(k=>{const o=document.createElement('option'); o.value=k; o.textContent=k; og.appendChild(o);});
    sf.appendChild(og);
  });
  if(fmts['Si 150 mm (675 um)']) sf.value='Si 150 mm (675 um)';
  ['spin_coating','ebeam_exposure','development','rie_etch','o2_plasma_treatment','rinse']
     .forEach(id=>addStep(id));
}
function addStep(preset){
  const wrap=document.getElementById('steps');
  const div=document.createElement('div'); div.className='step';
  const fams={}; SCHEMA.steps.forEach(s=>{(fams[s.family]=fams[s.family]||[]).push(s);});
  const opts=Object.keys(fams).map(f=>'<optgroup label="'+f+'">'+
     fams[f].map(s=>`<option value="${s.id}" ${s.id===preset?'selected':''}>${s.label}</option>`).join('')+
     '</optgroup>').join('');
  div.innerHTML=`<div class="step-head"><span class="badge"></span>
    <select class="stype" onchange="renderParams(this)"><option value="">— choose step —</option>${opts}</select>
    <div class="mv">
      <button class="icon" onclick="this.closest('.step').previousElementSibling&&this.closest('.step').parentNode.insertBefore(this.closest('.step'),this.closest('.step').previousElementSibling);renumber()">↑</button>
      <button class="icon" onclick="const s=this.closest('.step'),n=s.nextElementSibling;if(n)s.parentNode.insertBefore(n,s);renumber()">↓</button>
      <button class="icon" onclick="this.closest('.step').remove();renumber()">✕</button>
    </div></div><div class="stepnote muted"></div><div class="params"></div>`;
  wrap.appendChild(div);
  if(preset) renderParams(div.querySelector('.stype'));
  renumber();
}
function renderParams(sel){
  const stepEl=sel.closest('.step');
  const box=stepEl.querySelector('.params'); box.innerHTML='';
  const s=byId[sel.value];
  stepEl.querySelector('.stepnote').textContent = s ? (s.note||'') : '';
  if(!s) return;
  const adv=[];   // nameplate powers + fixed assumptions, collapsed below the primary knobs
  s.params.forEach(p=>{
    const d=document.createElement('div'); d.className='p';
    const title=p.about?` title="${p.about}"`:'';
    if(p.kind==='choice'){
      const o=p.choices.map(c=>`<option ${c==p.default?'selected':''}>${c}</option>`).join('');
      d.innerHTML=`<label${title}>${p.name}</label><select data-n="${p.name}" onchange="applyChoiceDefaults(this)">${o}</select>`;
    }else{
      const val=(p.default==null?'':p.default);
      d.innerHTML=`<label${title}>${p.name}${p.unit?' ('+p.unit+')':''}</label>
                   <input type="number" step="any" data-n="${p.name}" value="${val}">`;
    }
    if(p.advanced) adv.push(d); else box.appendChild(d);
  });
  if(adv.length){
    const det=document.createElement('details'); det.className='adv';
    det.innerHTML='<summary>advanced &middot; nameplate &amp; fixed assumptions</summary>';
    const g=document.createElement('div'); g.className='advgrid';
    adv.forEach(d=>g.appendChild(d)); det.appendChild(g); box.appendChild(det);
  }
  s.params.forEach(p=>{
    if(p.kind==='choice'){
      const el=box.querySelector(`[data-n="${p.name}"]`);
      if(el) applyChoiceDefaults(el);
    }
  });
}
function loadFlow(replace){
  const id=document.getElementById('flowSel').value;
  if(!id){alert('Pick a standard flow first.');return;}
  const f=(SCHEMA.flows||[]).find(x=>x.id===id); if(!f) return;
  if(replace) document.getElementById('steps').innerHTML='';
  f.steps.forEach(st=>{
    addStep(st.step_type);
    const el=document.querySelectorAll('.step');
    const stepEl=el[el.length-1];
    Object.keys(st.params||{}).forEach(k=>{
      const inp=stepEl.querySelector(`.params [data-n="${k}"]`);
      if(inp){ inp.value=st.params[k]; if(inp.tagName==='SELECT') applyChoiceDefaults(inp); }
    });
    // re-apply explicit params AFTER any choice-driven autofill, so the flow wins
    Object.keys(st.params||{}).forEach(k=>{
      const inp=stepEl.querySelector(`.params [data-n="${k}"]`);
      if(inp) inp.value=st.params[k];
    });
  });
  renumber();
  document.getElementById('status').textContent='Loaded: '+f.label+' ('+f.steps.length+' steps)';
}
function applyChoiceDefaults(sel){
  const stepEl=sel.closest('.step');
  const s=byId[stepEl.querySelector('.stype').value];
  const cd=s&&s.choice_defaults?s.choice_defaults[sel.dataset.n]:null;
  if(!cd) return;
  const vals=cd[sel.value]; if(!vals) return;
  Object.keys(vals).forEach(k=>{
    const el=stepEl.querySelector(`.params [data-n="${k}"]`);
    if(el) el.value=vals[k];
  });
}
function renumber(){[...document.querySelectorAll('.step')].forEach((s,i)=>s.querySelector('.badge').textContent=i+1);}
function collect(){
  let rows=[...document.querySelectorAll('.step')].map(s=>{
    const st=s.querySelector('.stype').value; if(!st) return null;
    const params={};
    s.querySelectorAll('.params [data-n]').forEach(el=>{if(el.value!=='')params[el.dataset.n]=el.value;});
    return {step_type:st, params};
  }).filter(Boolean);
  if(document.getElementById('incSub').checked){
    const nw=parseFloat(document.getElementById('nWaf').value)||1;
    const fmt=document.getElementById('subFormat').value;
    rows.unshift({step_type:'substrate', params:{wafer_format:fmt, n_wafers:nw}});
  }
  return rows;
}
function runOpts(){
  const fmt=document.getElementById('subFormat').value;
  const f=(SCHEMA.substrate_formats||{})[fmt];
  return {grid: document.getElementById('gridSel').value,
          voltage: document.getElementById('voltSel').value,
          wafer_diameter_mm: (f&&f.dia_mm)||150};
}
async function compute(){
  const rows=collect(); const stat=document.getElementById('status'); const res=document.getElementById('result');
  if(!rows.length){res.innerHTML='';stat.textContent='Add at least one step.';return;}
  stat.textContent='Computing…'; res.innerHTML='';
  try{
    const r=await fetch('/compute',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({rows,opts:runOpts()})});
    const d=await r.json(); stat.textContent='';
    if(d.error){res.innerHTML=`<div class="res err">Error: ${d.error}</div>`;return;}
    const max=Math.max(...d.steps.map(x=>Math.abs(x.gwp)),1e-9);
    const rowsHtml=d.steps.map(x=>`<tr>
        <td><b style="color:#8494ad;font-weight:600">${x.n}.</b> ${x.label}</td>
        <td style="width:34%"><div class="bar" style="width:${Math.max(1.5,100*Math.abs(x.gwp)/max)}%"></div></td>
        <td class="num"><b>${x.gwp.toFixed(3)}</b></td>
        <td class="num muted">${x.share.toFixed(1)}%</td></tr>`).join('');
    res.innerHTML=`<div class="res"><div class="total">${d.total.toFixed(2)} kg CO₂-eq</div>
      <div class="muted" style="margin-top:2px">Total cradle-to-gate GWP · ${d.method}</div>
      <table><thead><tr><th>Step — ranked by contribution</th><th></th>
        <th class="num">kg CO₂-eq</th><th class="num">share</th></tr></thead>
        <tbody>${rowsHtml}</tbody></table></div>`;
  }catch(e){stat.innerHTML='<span class="err">request failed</span>';}
}
async function download_db(){
  const rows=collect(); const stat=document.getElementById('status');
  if(!rows.length){stat.textContent='Add at least one step.';return;}
  stat.textContent='Building database…';
  try{
    const r=await fetch('/download',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({rows,opts:runOpts()})});
    if(!r.ok){stat.innerHTML='<span class="err">download failed</span>';return;}
    const blob=await r.blob(); const url=URL.createObjectURL(blob);
    const a=document.createElement('a'); a.href=url; a.download='LineBuilder_database.xlsx'; a.click();
    URL.revokeObjectURL(url); stat.textContent='';
  }catch(e){stat.innerHTML='<span class="err">download failed</span>';}
}
init();
</script></body></html>"""


@app.route("/")
def index():
    return Response(PAGE, mimetype="text/html")


@app.route("/schema")
def schema():
    return jsonify(core.get_schema())


@app.route("/compute", methods=["POST"])
def compute():
    try:
        body = request.get_json(force=True)
        return jsonify(core.compute(body["rows"], body.get("opts")))
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/download", methods=["POST"])
def download():
    body = request.get_json(force=True)
    rows = body["rows"]
    path = os.path.join(tempfile.gettempdir(), "LineBuilder_database.xlsx")
    core.export_excel(rows, path, body.get("opts"))
    return send_file(path, as_attachment=True, download_name="LineBuilder_database.xlsx")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"LineBuilder running at http://127.0.0.1:{port}")
    app.run(host="127.0.0.1", port=port, debug=False)
