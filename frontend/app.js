// ---- result state + rendering (real data from the pipeline) ----
let currentResult = null;

const esc = s => (s==null?'':String(s)).replace(/[&<>]/g, m=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[m]));
const cap = s => (s||'').charAt(0).toUpperCase()+(s||'').slice(1);

// tiny markdown renderer (headings, bold/italic, lists, paragraphs, [PMID ..] highlighted)
function md(text){
  if(!text) return '';
  const lines = String(text).split(/\r?\n/); let html='', list=false;
  const inline = t => esc(t)
    .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
    .replace(/(?<!\*)\*(?!\*)(.+?)\*(?!\*)/g,'<em>$1</em>')
    .replace(/PMID[:\s]*\d+/gi, m=>`<a class="cite" data-go="citations">${m}</a>`);
  for(let ln of lines){
    if(/^\s*[-*]\s+/.test(ln)){ if(!list){html+='<ul>';list=true;} html+='<li>'+inline(ln.replace(/^\s*[-*]\s+/,''))+'</li>'; continue; }
    if(list){html+='</ul>';list=false;}
    const h=ln.match(/^(#{1,4})\s+(.*)$/);
    if(h){ const n=h[1].length; html+=`<h${n+1}>`+inline(h[2])+`</h${n+1}>`; }
    else if(ln.trim()==='') {}
    else html+='<p>'+inline(ln)+'</p>';
  }
  if(list) html+='</ul>';
  return html;
}

function renderAnswer(d){
  const claims = d.claims.filter(c=>!c.is_abstention);
  const abst = d.claims.filter(c=>c.is_abstention);
  const contested = claims.filter(c=>c.consensus_label==='contested').length;
  const meta = [];
  if(claims.length) meta.push(`<span class="tag ${strongestTag(claims)}">${claims.length} claim${claims.length>1?'s':''}</span>`);
  if(contested) meta.push(`<span class="cpill"><span class="star">★</span> ${contested} contested</span>`);
  if(abst.length) meta.push(`<span class="tag low">${abst.length} abstention${abst.length>1?'s':''}</span>`);
  if(d.retrieval_mode==='degraded') meta.push(`<span class="tag moderate">degraded retrieval</span>`);
  document.getElementById('answerMeta').innerHTML = meta.join('');
  // Answer tab = the short crux only: one paragraph, no citations, no claim cards.
  // (Full graded claims live in Explanation; sources live in Citations.)
  const crux = (d.narrative_md || '').replace(/\s*\[?PMID[:\s]*\d+\]?/gi, '');
  document.getElementById('answerNarrative').innerHTML = `<div class="crux">${md(crux)}</div>`;
}
function strongestTag(claims){
  if(claims.some(c=>c.evidence_strength==='high')) return 'high';
  if(claims.some(c=>c.evidence_strength==='moderate')) return 'moderate';
  return 'low';
}

function renderExplanation(d){
  document.getElementById('explanationBody').innerHTML = md(d.explanation_md) || '<p class="footnote">No detailed explanation for this run.</p>';
}

function renderCites(){
  const rows = (currentResult?.citations)||[];
  document.getElementById('citeBody').innerHTML = rows.length ? rows.map((c,i)=>{
    const pmid = c.source_ref.replace('PMID:','');
    const link = `https://pubmed.ncbi.nlm.nih.gov/${pmid}/`;
    const rel = c.relevance||0;
    return `<tr>
      <td class="num">${i+1}</td>
      <td><a class="src" href="${link}" target="_blank" rel="noopener">${esc(c.source_ref)}</a></td>
      <td>${esc(c.title)}${c.contested?' <span class="cpill"><span class="star">★</span> contested</span>':''}</td>
      <td>${esc(c.journal)}</td>
      <td><span class="tag ${c.confidence}">${cap(c.confidence)}</span></td>
      <td><div style="display:flex;align-items:center;gap:8px"><div class="bar"><i style="width:${rel}%"></i></div><span class="num">${rel}%</span></div></td>
    </tr>`;
  }).join('') : `<tr><td colspan="6" class="footnote">No citations for this run.</td></tr>`;
}

function renderStats(d){
  const s = d.summary||{};
  document.getElementById('statsCards').innerHTML = `
    <div class="card"><h4>Run summary</h4>
      <div class="kpi"><span>Citations (unique papers)</span><b>${s.citations||0}</b></div>
      <div class="kpi"><span>Claims verified</span><b>${s.claims||0}</b></div>
      <div class="kpi"><span>Abstentions</span><b>${s.abstentions||0}</b></div>
    </div>
    <div class="card"><h4>Cost &amp; latency (this run)</h4>
      <div class="kpi"><span>Total tokens (Groq)</span><b>${(s.tokens||0).toLocaleString()}</b></div>
      <div class="kpi"><span>Total latency</span><b>${((s.total_ms||0)/1000).toFixed(1)}s</b></div>
      <div class="kpi"><span>Retrieval mode</span><b style="font-size:15px">${esc(d.retrieval_mode)}</b></div>
    </div>`;
  document.getElementById('statsTrace').innerHTML = (d.stage_logs||[]).map(s=>`
    <tr><td class="num">${esc(s.stage_no)}</td><td>${esc(cap(s.agent_id.replace('_','-')))}</td>
    <td>${esc(s.model_id||'—')}</td><td class="num">${(s.latency_ms/1000).toFixed(1)} s</td>
    <td class="num">${(s.tokens||0).toLocaleString()}</td>
    <td><span class="tag ${/degraded|drop/.test(s.status)?'moderate':'high'}">${esc(s.status)}</span></td></tr>`).join('');
  document.getElementById('statsNote').innerHTML = (d.flags&&d.flags.length)
    ? 'Flags: '+d.flags.map(esc).join(', ')+'. Open the <b>Log</b> for the execution timeline.'
    : 'Open the <b>Log</b> for the execution timeline.';
}

function renderGantt(){
  const logs = (currentResult?.stage_logs)||[];
  const total = logs.reduce((s,r)=>s+(r.latency_ms||0),0) || 1;
  let acc=0;
  document.getElementById('ganttRows').innerHTML = logs.map(s=>{
    const dur=(s.latency_ms||0)/1000; const left=(acc/total)*100, width=Math.max((s.latency_ms/total)*100,2); acc+=s.latency_ms||0;
    const cls = /degraded|drop/.test(s.status)?'warn':(/70b/.test(s.model_id||'')?'big':'');
    return `<div class="logrow">
      <div class="agent"><div class="nm"><span class="idx">${esc(s.stage_no)}</span>${esc(cap(s.agent_id.replace('_','-')))}</div><div class="role">${esc(s.status)}</div></div>
      <div class="track"><div class="gbar ${cls}" style="left:${left}%;width:${width}%">${dur.toFixed(1)}s</div></div>
    </div>`;
  }).join('');
  document.getElementById('logTotal').textContent = (total/1000).toFixed(1)+' s';
  const meta = document.querySelector('.logmeta');
  if(meta) meta.innerHTML = `<div><span class="label">Pipeline</span><b>${logs.length} stages</b></div>`+
    `<div><span class="label">Mode</span><b style="color:var(--brass)">${esc(currentResult?.retrieval_mode||'')}</b></div>`;
  const notes=[];
  if(currentResult?.retrieval_mode==='degraded') notes.push('Retriever ran in <b>degraded mode</b> (live PubMed unavailable).');
  const corr=logs.find(s=>s.agent_id==='corroborator');
  const m=corr && /(\d+)\s*dropped/.exec(corr.status||'');
  if(m && +m[1]>0) notes.push(`Corroborator dropped <b>${m[1]}</b> uncorroborated relation${+m[1]>1?'s':''} before the claim chain.`);
  const flag=document.getElementById('logFlag');
  if(notes.length){ flag.innerHTML='<b>Note:</b> '+notes.join(' '); flag.hidden=false; } else flag.hidden=true;
}

// ---- auth (real API · researcher-only) ----
const API = "/api/v1";
const store = {
  get access(){ return localStorage.getItem("solace_access"); },
  get refresh(){ return localStorage.getItem("solace_refresh"); },
  set(a,r){ if(a) localStorage.setItem("solace_access",a); if(r) localStorage.setItem("solace_refresh",r); },
  clear(){ localStorage.removeItem("solace_access"); localStorage.removeItem("solace_refresh"); },
};
let currentUser = null;
let authMode = "login";

const loginView=document.getElementById('loginView'),
      homeView=document.getElementById('homeView'),
      resultsView=document.getElementById('resultsView');

async function api(path, {method="GET", body=null, auth=false}={}){
  const headers={"Content-Type":"application/json"};
  if(auth && store.access) headers["Authorization"]=`Bearer ${store.access}`;
  let res = await fetch(API+path,{method,headers,body:body?JSON.stringify(body):null});
  if(res.status===401 && auth && store.refresh){
    const rr = await fetch(API+"/auth/refresh",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({refresh_token:store.refresh})});
    if(rr.ok){ const rd=await rr.json(); store.set(rd.access_token, rd.refresh_token||null);
      headers["Authorization"]=`Bearer ${store.access}`;
      res = await fetch(API+path,{method,headers,body:body?JSON.stringify(body):null});
    }
  }
  return res;
}

function acctChipHTML(){
  if(!currentUser) return '';
  const nm = currentUser.display_name || currentUser.email;
  return `<span class="chip-user"><span class="nm">${nm}</span>`+
         `<span class="rolepill researcher">researcher</span></span>`+
         `<button class="acctbtn js-logout">Log out</button>`;
}
function paintAccount(){
  document.getElementById('acctHome').innerHTML = acctChipHTML();
  document.querySelectorAll('.js-logout').forEach(b=>b.addEventListener('click',logout));
}

function setAuthMode(mode){
  authMode = mode;
  const reg = mode==="register";
  document.getElementById('nameField').hidden = !reg;
  document.getElementById('loginSub').textContent = reg ? "Create your researcher account" : "Sign in to your evidence workbench";
  document.getElementById('loginSubmit').textContent = reg ? "Create account" : "Sign in";
  document.getElementById('toggleMode').textContent = reg ? "Have an account? Sign in" : "New here? Create an account";
  document.getElementById('loginErr').textContent = "";
}

async function submitAuth(){
  const email=document.getElementById('loginEmail').value.trim();
  const pass=document.getElementById('loginPass').value;
  const err=document.getElementById('loginErr'); err.textContent="";
  if(!email || !pass){ err.textContent="Email and password are required."; return; }
  const path = authMode==="register" ? "/auth/register" : "/auth/login";
  const body = authMode==="register"
    ? {email,password:pass,display_name:document.getElementById('loginName').value.trim()||null}
    : {email,password:pass};
  try{
    const res=await api(path,{method:"POST",body});
    const data=await res.json().catch(()=>({}));
    if(!res.ok){ err.textContent = data.detail ? String(data.detail) : `Error ${res.status}`; return; }
    store.set(data.access_token, data.refresh_token);
    currentUser = data.user;
    loginView.classList.add('hidden');
    showHome();
  }catch(e){ err.textContent="Network error — is the server running?"; }
}

async function logout(){
  try{ if(store.refresh) await api("/auth/logout",{method:"POST",body:{refresh_token:store.refresh}}); }catch(e){}
  store.clear(); currentUser=null; closeLog();
  [homeView,resultsView].forEach(v=>v.classList.add('hidden'));
  loginView.classList.remove('hidden'); window.scrollTo(0,0);
}

async function restoreSession(){
  if(!store.access){ loginView.classList.remove('hidden'); return; }
  const res = await api("/auth/me",{auth:true});
  if(res.ok){ currentUser = await res.json(); loginView.classList.add('hidden'); showHome(); }
  else { store.clear(); loginView.classList.remove('hidden'); }
}

function showHome(){ closeLog(); resultsView.classList.add('hidden'); homeView.classList.remove('hidden'); paintAccount(); window.scrollTo(0,0); }

// ---- run a query (real pipeline) ----
let _stepTimer=null;
function setLoading(on){
  const ov=document.getElementById('loadingOverlay');
  ov.classList.toggle('show', on);
  if(on){ const steps=["decomposing question…","searching PubMed…","building & corroborating relations…","fact-checking & grading…","synthesizing…"]; let i=0;
    const el=document.getElementById('loadingSteps'); el.textContent=steps[0];
    _stepTimer=setInterval(()=>{ i=(i+1)%steps.length; el.textContent=steps[i]; }, 3500);
  } else if(_stepTimer){ clearInterval(_stepTimer); _stepTimer=null; }
}
function showRunError(msg){
  document.getElementById('answerMeta').innerHTML='';
  document.getElementById('answerNarrative').innerHTML=`<div class="runerr"><b>Could not complete the review.</b><br>${esc(msg)}</div>`;
  document.getElementById('explanationBody').innerHTML='';
  document.getElementById('citeBody').innerHTML='';
  document.getElementById('statsCards').innerHTML=''; document.getElementById('statsTrace').innerHTML='';
  selectTab('answer');
}
function renderAll(d){ renderAnswer(d); renderExplanation(d); renderStats(d); renderCites(); selectTab('answer'); }

async function runQuery(q){
  q=(q||'').trim();
  if(q.length<5){ document.getElementById('queryInput').focus(); return; }
  document.getElementById('questionText').textContent=q;
  homeView.classList.add('hidden'); resultsView.classList.remove('hidden'); window.scrollTo(0,0);
  setLoading(true);
  try{
    const res = await api('/queries',{method:'POST',body:{query:q},auth:true});
    if(res.status===401){ setLoading(false); logout(); return; }
    const data = await res.json().catch(()=>({}));
    if(!res.ok){ showRunError(data.detail || ('Error '+res.status)); return; }
    currentResult = data; renderAll(data);
  }catch(e){ showRunError('Network error while running the pipeline.'); }
  finally{ setLoading(false); }
}

// ---- tabs ----
const TABS=['answer','explanation','citations','stats'];
function selectTab(name){
  document.querySelectorAll('#tabBar .tab').forEach(t=>t.setAttribute('aria-selected', t.dataset.tab===name?'true':'false'));
  TABS.forEach(t=>document.getElementById('tab-'+t).classList.toggle('hidden', t!==name));
  if(name==='citations') renderCites();
  window.scrollTo({top:0,behavior:'smooth'});
}

// ---- log panel ----
const scrim=document.getElementById('scrim'), logPanel=document.getElementById('logPanel');
function openLog(){ renderGantt(); scrim.classList.add('show'); logPanel.classList.add('show'); logPanel.setAttribute('aria-hidden','false'); }
function closeLog(){ scrim.classList.remove('show'); logPanel.classList.remove('show'); logPanel.setAttribute('aria-hidden','true'); }

// ---- auth wiring ----
document.getElementById('loginForm').addEventListener('submit',e=>{e.preventDefault();submitAuth();});
document.getElementById('toggleMode').addEventListener('click',()=>setAuthMode(authMode==="login"?"register":"login"));

// ---- wiring ----
document.getElementById('submitBtn').addEventListener('click',()=>runQuery(document.getElementById('queryInput').value));
document.getElementById('queryInput').addEventListener('keydown',e=>{if((e.metaKey||e.ctrlKey)&&e.key==='Enter')runQuery(e.target.value);});
document.querySelectorAll('#exampleChips .chip').forEach(c=>c.addEventListener('click',()=>runQuery(c.textContent)));
document.getElementById('tabBar').addEventListener('click',e=>{const t=e.target.closest('.tab'); if(t)selectTab(t.dataset.tab);});
document.addEventListener('click',e=>{const el=e.target.closest('[data-go]'); if(el){e.preventDefault();selectTab(el.dataset.go);}});
document.getElementById('backBtn').addEventListener('click',showHome);
document.getElementById('brandHome').addEventListener('click',showHome);
document.getElementById('logBtn').addEventListener('click',openLog);
document.getElementById('logClose').addEventListener('click',closeLog);
scrim.addEventListener('click',closeLog);
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeLog();});

// ---- PDF export (real) ----
const toast=document.getElementById('toast');
document.getElementById('downloadBtn').addEventListener('click',async ()=>{
  if(!currentResult){ return; }
  toast.classList.add('show');
  try{
    const res = await api(`/queries/${currentResult.query_id}/export?format=pdf`,{auth:true});
    if(!res.ok){ throw new Error(res.status); }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href=url; a.download=`solace-${currentResult.query_id.slice(0,8)}.pdf`;
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
  }catch(e){ /* ignore */ }
  setTimeout(()=>toast.classList.remove('show'),1500);
});

// restore session on load (if a valid token is stored)
restoreSession();
