"use strict";
const $ = s => document.querySelector(s);
const esc = v => String(v ?? "").replace(/[&<>"']/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const icons={grid:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',layers:'<path d="m12 3 10 5-10 5L2 8z M3 12l9 5 9-5 M3 16l9 5 9-5"/>',ledger:'<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6m-6 4h6m-6 4h4"/>',people:'<circle cx="9" cy="8" r="3"/><path d="M3 20v-2a6 6 0 0 1 12 0v2m0-15a3 3 0 0 1 0 6m3 4a5 5 0 0 1 3 4"/>',check:'<path d="m4 12 5 5L20 6"/>',clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v6l4 2"/>',arrow:'<path d="M5 12h14m-5-5 5 5-5 5"/>',rupee:'<path d="M5 5h14M5 9h14M8 5c7 0 8 8-2 8l9 7"/>',pin:'<path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0Z"/><circle cx="12" cy="10" r="2"/>',book:'<path d="M4 5h7l1 2 1-2h7v14h-7l-1 1-1-1H4z"/>',calendar:'<rect x="3" y="5" width="18" height="15" rx="2"/><path d="M7 3v4m10-4v4M3 10h18"/>',shield:'<path d="m12 2 8 4v5c0 5-4 9-8 11-4-2-8-6-8-11V6z"/><path d="m8 11 3 3 5-6"/>'};
const icon=k=>'<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">'+(icons[k]||icons.grid)+'</svg>';
const num=n=>Number(n||0).toLocaleString("en-IN"), money=n=>"₹"+Number(n||0).toLocaleString("en-IN",{maximumFractionDigits:2});
const shortMoney=n=> Math.abs(n)>=1e7?"₹"+(n/1e7).toFixed(2)+"Cr":Math.abs(n)>=1e5?"₹"+(n/1e5).toFixed(2)+"L":money(n);
const date=v=>{if(!v)return "—";const d=new Date(String(v).slice(0,10)+"T12:00:00Z");return Number.isNaN(+d)?esc(v):new Intl.DateTimeFormat("en-GB",{day:"numeric",month:"short",year:"numeric",timeZone:"UTC"}).format(d)};
const human=v=>String(v||"").replaceAll("_"," ").toLowerCase().replace(/^./, c=>c.toUpperCase());
const color=v=>["Eligible","VERIFIED","CANCELLED_VERIFIED","APPROVED"].includes(v)?"good":["MISMATCH","Ineligible"].includes(v)?"bad":["PENDING_EVENT","Review","OBJECTED","NOTIFIED"].includes(v)?"warn":"neutral";
const tag=(v,label)=>'<span class="tag '+color(v)+'">'+esc(label||human(v))+'</span>';
const btn=(action,label,kind="",attrs="")=>'<button type="button" class="btn '+kind+'" data-do="'+action+'" '+attrs+'>'+label+'</button>';
let data, view="overview", preview="occurrence", search="",filter="All",onlyChanges=false,page=0, selectedPlan="",busy=false,toastTimer;
const names={overview:"Event overview",rules:"Reading check",ledger:"Booking ledger"};
const wf=()=>data.workflow;
const activeReading=()=>data.settings?.reading||"occurrence";
const head=(title,subtitle,control="")=>'<div class="page-heading"><div><h1>'+title+'</h1><p>'+subtitle+'</p></div>'+control+'</div>';
const cardhead=(name,sub,action="")=>'<div class="card-head"><div><h2>'+name+'</h2>'+(sub?'<div class="kicker">'+sub+'</div>':'')+'</div>'+action+'</div>';
const stat=(ic,label,value,hint)=>'<div class="stat"><div class="stat-label">'+icon(ic)+label+'</div><strong>'+value+'</strong><small>'+hint+'</small></div>';
const field=(label,value)=>'<span class="datum">'+label+'<strong>'+esc(value)+'</strong></span>';
function overview(){
 const {event,clock,metrics:m}=data,pct=Math.max(0,Math.min(100,(clock.elapsed||0)/135*100));
 return head("Event overview","Find affected borrowers, review relief terms and verify each booking.",btn("sources",icon("book")+" Event brief"))+
 '<section class="hero"><canvas id="landscape" aria-hidden="true"></canvas><div class="hero-info"><div class="eyebrow">'+icon("pin")+' ACTIVE DISASTER EVENT</div><h2>Andhra Pradesh drought</h2><p>Relief for borrowers in drought-affected mandals.</p><div class="hero-foot"><span>'+esc(event.id)+'</span><span>DEMO DECLARATION · '+date(event.declared_on).toUpperCase()+'</span></div></div><span class="image-label">ILLUSTRATIVE TERRAIN</span></section>'+
 '<div class="stats">'+stat("people","Borrowers assessed",num(m.total),"Across the synthetic portfolio")+stat("check","Eligible borrowers",num(m.eligible),(100*m.eligible/m.total).toFixed(1)+"% of assessed borrowers")+stat("layers","Needs review",num(m.review),"Officer review required")+stat("rupee","Added provision",shortMoney(m.provision),"Eligible borrower exposure")+'</div>'+
 '<div class="cols"><section class="panel">'+cardhead("Implementation clock","Calendar days from the declaration",tag("APPROVED","Day "+clock.elapsed+" of 135"))+'<div class="clock-num">'+num(clock.days_left)+'<small>days remaining</small></div><div class="clock-track" role="img" aria-label="'+pct.toFixed(0)+' percent elapsed"><b style="width:'+pct+'%"></b><i style="left:'+pct+'%"></i></div><div class="axis"><span>DAY 0</span><span>DAY 135</span></div><div class="clock-footer">'+field("Implementation deadline",date(clock.deadline))+field("Required pace",clock.needed_per_day==null?"Window closed":num(clock.needed_per_day)+" / day")+field("Achieved (7 days)",num(clock.achieved_per_day)+" / day")+'</div></section>'+
 '<section class="panel">'+cardhead("Borrower outcomes","Using the approved test date",btn("rules",icon("arrow"),"","aria-label=\"Inspect reading check\""))+'<div class="bar" aria-hidden="true">'+[m.eligible,m.review,m.ineligible].map(n=>'<b style="flex:'+n+'"></b>').join("")+'</div>'+[["Eligible",m.eligible,""],["Needs review",m.review,"warn"],["Ineligible",m.ineligible,"neutral"]].map(([label,n,c])=>'<div class="row"><span><i class="dot '+c+'"></i>'+label+'</span><strong>'+num(n)+'</strong></div>').join("")+'</section></div>'+
 '<div class="cols"><section class="panel">'+cardhead("Affected mandals","Synthetic borrower distribution by event area")+'<div class="scroll"><table class="listing"><thead><tr><th>Mandal</th><th>Drought tier</th><th>Borrowers</th></tr></thead><tbody>'+event.mandals.map(x=>'<tr><td>'+esc(x.name)+'</td><td>'+esc(human(x.tier))+'</td><td>'+num(x.count)+'</td></tr>').join("")+'</tbody></table></div></section><section class="panel">'+cardhead("Event milestones","Deadlines under the selected counting convention")+clock.milestones.concat([{label:"Last safe business day",date:clock.last_safe_business_day},{label:"Projected approval finish at current pace",date:clock.projected_finish}]).map(x=>'<div class="row"><span>'+esc(x.label)+'</span><strong class="mono">'+date(x.date)+'</strong></div>').join("")+'<div class="inset"><small>Borrower-requested invocation follows its own deadline. Bank-initiated relief is deemed invoked on the committee recommendation.</small></div></section></div>';
}
// A procedural contour illustration stays crisp at every viewport and works offline.
function terrain(){
 const cv=$("#landscape");if(!cv)return;const w=cv.clientWidth,h=cv.clientHeight,scale=Math.min(2,devicePixelRatio||1);
 cv.width=w*scale;cv.height=h*scale;const c=cv.getContext("2d");c.scale(scale,scale);c.fillStyle="#263422";c.fillRect(0,0,w,h);
 c.save();c.translate(w*.76,h*.47);c.scale(w/880,h/190);
 for(let k=0;k<122;k++){let radius=6+k*3.7;c.beginPath();for(let i=0;i<=260;i++){let a=i*2*Math.PI/260;
 const mod=1+.17*Math.sin(3*a+k*.011)+.104*Math.sin(5*a+.35)+.043*Math.cos(8*a-k*.01);
 const x=radius*mod*Math.cos(a)*1.4+Math.sin(radius/29)*4,y=radius*mod*Math.sin(a)*.63+Math.sin(x/65)*12;
 if(i)c.lineTo(x,y);else c.moveTo(x,y)}
 c.strokeStyle=k%6===0?"rgba(211,230,151,.64)":"rgba(178,203,143,.40)";c.lineWidth=k%6===0?1.15:.7;c.stroke();}
 c.restore();c.fillStyle="rgba(213,239,177,.23)";for(let x=w*.55;x<w;x+=42)for(let y=13;y<h;y+=42){c.fillRect(x-2,y,5,.7);c.fillRect(x,y-2,.7,5)}
}
function readingImpact(selected, approved) {
 if (selected.id === approved.id) return '<p class="muted">Choose another date to see who moves into or out of eligibility.</p>';
 const gained = selected.flips.filter(f => f.to_status === "Eligible").length;
 const lost = selected.flips.filter(f => f.from_status === "Eligible").length;
 const amount = selected.provision - approved.provision;
 return '<div class="impact-summary" aria-live="polite"><strong>'+num(selected.flips.length)+' borrowers change status</strong><span>'+num(gained)+' become eligible, '+num(lost)+' lose eligibility</span><span>Provision '+(amount<0?'falls':'rises')+' by '+shortMoney(Math.abs(amount))+'</span></div>';
}
function rules(){
 const rs=data.readings,sel=rs.find(r=>r.id===preview)||rs[0],active=activeReading();
 return head("Reading check","See which borrowers change outcome when the test date changes.",btn("sources",icon("book")+" Rule evidence"))+
 '<section class="panel">'+cardhead("Compare eligibility dates","Same portfolio · "+num(data.metrics.total)+" synthetic borrowers",tag("APPROVED","Approved: "+human(active)))+
 '<div class="rule-options">'+rs.map(r=>'<button class="rule-card" data-do="preview" data-id="'+esc(r.id)+'" aria-pressed="'+(sel.id===r.id)+'"><span>'+esc(r.label)+'</span><small>'+date(r.date)+'</small><div class="rule-fill"><b style="width:'+(100*r.eligible/data.metrics.total)+'%"></b></div><strong>'+num(r.eligible)+'</strong><small>ELIGIBLE BORROWERS</small></button>').join("")+'</div><div class="between">'+readingImpact(sel,rs.find(r=>r.id===active))+btn("reading-approval","Review settings "+icon("arrow"))+'</div></section>'+
 '<section class="panel section-gap">'+cardhead("Borrower register","Select a borrower to inspect facilities, evidence and repayment options.")+'<div class="tools"><div class="chips"><input id="search" type="search" placeholder="Search name or ID" aria-label="Search borrower name or ID" value="'+esc(search)+'"><select class="select" id="filter" aria-label="Filter by eligibility">'+["All","Eligible","Ineligible","Review"].map(x=>'<option '+(filter===x?'selected':'')+'>'+x+'</option>').join("")+'</select></div><label><input id="flips" type="checkbox" '+(onlyChanges?'checked':'')+'> Changed only</label></div><div id="register"></div></section>'+policyPanels();
}
function renderRegister(){
 const sel=data.readings.find(r=>r.id===preview)||data.readings[0], changes=new Map(sel.flips.map(f=>[f.id,f]));
 const rows=data.borrowers.map(b=>({b,change:changes.get(b.id)})).filter(({b,change})=>(!onlyChanges||change)&&(filter==="All"||(change?.to_status||b.status)===filter)&&(b.name+" "+b.id).toLowerCase().includes(search.toLowerCase()));
 page=Math.max(0,Math.min(page,Math.ceil(rows.length/8)-1));
 $("#register").innerHTML='<div class="scroll"><table class="listing"><thead><tr><th>Borrower</th><th>Mandal</th><th>Outstanding</th><th>Preview outcome</th><th>Change</th></tr></thead><tbody>'+rows.slice(page*8,page*8+8).map(({b,change})=>'<tr><td><button class="row-link" data-do="borrower" data-id="'+esc(b.id)+'">'+esc(b.name)+'</button><small>'+esc(b.id)+'</small></td><td>'+esc(b.mandal)+'</td><td>'+money(b.outstanding)+'</td><td>'+tag(change?.to_status||b.status)+'</td><td>'+esc(change?change.from_status+" → "+change.to_status:"—")+'</td></tr>').join("")+'</tbody></table></div>'+(rows.length?"":'<p class="empty">No borrowers match these filters.</p>')+'<div class="pager"><span>'+num(rows.length)+' borrowers · Page '+(page+1)+' of '+Math.max(1,Math.ceil(rows.length/8))+'</span><div class="actions">'+btn("prev","Previous","",page===0?"disabled":"")+btn("next","Next","",(page+1)*8>=rows.length?"disabled":"")+'</div></div>';
}
function ledger(){
 const w=wf(),plans=w.plans||[],p=plans.find(x=>x.id===selectedPlan)||plans.find(x=>x.status==="MISMATCH")||plans[0]; if(p)selectedPlan=p.id;
 return head("Booking ledger","Compare each booking with the repayment schedule the officer approved.",'<div class="actions">'+btn("date-tools",icon("calendar")+" Demo controls")+btn("batch-tools","Manage batch","primary")+'</div>')+
 '<div class="stats">'+stat("ledger","Relief plans",num(plans.length),"In this workspace")+stat("shield","Verified bookings",num(plans.filter(x=>x.status==="VERIFIED").length),"Match approved schedules")+stat("layers","Mismatches",num(plans.filter(x=>x.status==="MISMATCH").length),"Require reconciliation")+stat("check","Audit chain",w.chain_valid?"Valid":"Failed",num(w.ledger.length)+" recorded entries")+'</div>'+
 '<div class="cols ledger-layout"><section class="panel">'+cardhead("Relief plans","Select an account to inspect its booking.")+'<div class="ledger-rows">'+plans.map(x=>'<button class="ledger-choice" data-do="plan" data-id="'+esc(x.id)+'" aria-pressed="'+(x.id===p?.id)+'"><span><strong>'+esc(x.name)+'</strong><small>'+esc(x.borrower_id)+'</small></span>'+tag(x.status)+'</button>').join("")+'</div></section><section class="panel">'+(p?planDetail(p):'<p class="empty">Draft a plan from an eligible borrower in Reading check.</p>')+'</section></div>'+
 '<section class="panel">'+cardhead("Audit trail","Most recent activity · hash-linked records")+[...w.ledger].sort((a,b)=>b.seq-a.seq).slice(0,12).map(x=>'<div class="ledger-event"><time>'+date(x.day)+'</time><div><strong>'+esc(human(x.kind))+'</strong> · '+esc(x.message)+'<small>'+esc(x.plan_id||"Event")+' · '+esc(String(x.hash).slice(0,16))+'</small></div></div>').join("")+'</section>';
}
function planDetail(p){
 const a=p.approved||{},b=p.booked||{},status=p.status,ds=p.diff||[],w=wf();let controls="";
 if(status==="DRAFT")controls=btn("approve-modal","Approve relief plan","primary");
 if(status==="APPROVED")controls=btn("notify","Issue simulated notice","primary");
 if(status==="NOTIFIED"){if(String(w.as_of)<=String(p.objection_deadline))controls=btn("object","Record objection")+btn("date-tools","Advance demo date","primary");
 else if(!w.paused&&!w.kill_switch)controls=btn("book-modal","Book and verify","primary");}
 if(status==="PENDING_EVENT")controls=btn("reconcile","Read back schedule");
 if(status==="VERIFIED")controls+=btn("opt-modal","Review opt-out");
 return cardhead(esc(p.name),esc(p.borrower_id)+" · "+esc(p.facility_id),tag(status))+
 '<div class="details-grid">'+field("Relief type",p.approved?.type==="CONVERSION"||p.relief_type==="CONVERSION"?"Crop-loan conversion":"Payment holiday")+field(p.status==="CANCELLED_VERIFIED"?"Provision after reversal":"Added provision",money(p.status==="CANCELLED_VERIFIED"?p.posted_provision:p.provision))+field("Core reference",p.txn_ref||"Awaiting booking")+'</div>'+
 (w.paused?'<div class="inset"><strong class="red">Booking batch paused</strong><p>Inspect the schedule difference before processing further bookings.</p></div>':'')+
 '<h3>Schedule check</h3><div class="scroll"><table class="listing"><thead><tr><th>Schedule field</th><th>Approved / simulated</th><th>Booked</th></tr></thead><tbody>'+
 [["First repayment","first_due",date],["Monthly instalment","emi",money],["Extra interest","extra_interest",money],["Moratorium","moratorium_months",v=>v+" months"],["Repayment term","tenor",v=>v+" months"]].map(([l,k,fmt])=>'<tr><td>'+l+'</td><td>'+(a[k]!=null?fmt(a[k]):"—")+'</td><td class="'+(a[k]!=null&&b[k]!=null&&a[k]!==b[k]?"red":"")+'">'+(b[k]!=null?fmt(b[k]):"—")+'</td></tr>').join("")+'</tbody></table></div>'+
 (ds.length?'<div class="inset"><div class="eyebrow red">SCHEDULE DIFFERENCES</div>'+ds.map(d=>'<div class="row"><span>'+esc(human(d.field))+'</span><span>'+esc(d.approved)+' → '+esc(d.booked)+'</span></div>').join("")+'</div>':'')+
 (p.notice?'<details class="inset"><summary>Borrower notice</summary><p>'+esc(p.notice)+'</p><small>Objection deadline · '+date(p.objection_deadline)+'</small></details>':'')+
 '<div class="actions section-gap">'+controls+btn("lineage","View lineage")+'</div>';
}
function modal(title,body){const d=$("#detail");$("#detail-body").innerHTML='<div class="modal-head"><h2>'+esc(title)+'</h2>'+btn("close","×","x",'aria-label="Close dialog"')+'</div>'+body;if(!d.open)d.showModal()}
function sources(){modal("Event brief",'<div class="eyebrow">'+esc(data.event.rule_version)+' · AP DROUGHT</div><div class="details-grid">'+field("Occurrence",date(data.event.occurrence))+field("Declaration",date(data.event.declared_on))+field("Committee",date(data.event.committee_date))+'</div>'+data.event.sources.map(s=>'<div class="source"><strong>'+esc(s.title)+'</strong><p>'+esc(s.excerpt)+'</p><small>'+esc(s.label)+'</small> '+(/^https?:\/\//.test(s.url||"")?'<a target="_blank" rel="noopener" href="'+esc(s.url)+'">Open source ↗</a>':'')+'</div>').join("")+'<button class="btn" data-open-evidence>Open evidence desk</button>')}
function borrower(id){
 const b=data.borrowers.find(x=>x.id===id);if(!b)return;$("#detail").dataset.borrower=id;
 const changed=data.readings.find(r=>r.id===preview)?.flips.find(x=>x.id===id);
 const pp=b.prudential||{},existing=wf().plans.find(x=>x.facility_id===b.facility_id);
 modal(b.name,'<div class="between"><span class="mono">'+esc(b.id)+' · '+esc(b.mandal)+'</span>'+tag(changed?.to_status||b.status)+'</div><div class="inset"><div class="eyebrow">'+esc(human(preview))+' DATE PREVIEW</div><p>'+esc(changed?.to_status==="Eligible"?"All eligibility checks pass on this date.":changed?.reason||b.reason)+'</p></div>'+
 '<h3>Loan facilities on the selected date</h3><div class="scroll"><table class="listing"><thead><tr><th>Facility</th><th>Balance</th><th>Overdue</th><th>Class</th></tr></thead><tbody>'+b.facilities.map(f=>{let s=f.snapshots[preview];return '<tr><td>'+esc(f.product)+'<small>'+esc(f.id)+'</small></td><td>'+money(f.principal)+'</td><td>'+(s?s.dpd+" days":"Missing")+'</td><td>'+esc(s?.classification||"Review")+'</td></tr>'}).join("")+'</tbody></table></div>'+
 '<div class="details-grid">'+field("Approved reading",human(activeReading()))+field("Current provision",money(b.provision))+field("Write-back target",money(pp.repayment_target))+'</div>'+
 (preview!==activeReading()?'<div class="inset"><strong>Preview only</strong><p>Repayment options use the officer-approved test date. Return to that reading to draft a plan.</p>'+btn("approved-preview","Show approved reading")+'</div>':b.plans.length?'<h3>Repayment options</h3><p class="kicker">'+(b.relief_type==="CONVERSION"?"Crop loan → term loan · original bullet due "+money(b.plans[0].original_maturity_due):"Instalment loan · original instalment "+money(b.plans[0].original_emi))+'</p>'+b.plans.map(p=>'<div class="row"><span><strong>Option '+esc(p.id)+'</strong> · '+num(p.months)+' instalments<small style="display:block">'+money(p.emi)+' / month · '+money(p.extra_interest)+' extra interest</small></span>'+(existing&&existing.status!=="DRAFT"?btn("existing-plan","Open signed plan","","data-id=\""+esc(existing.id)+"\""):btn("draft","Draft plan","","data-id=\""+esc(id)+"\" data-option=\""+esc(p.id)+"\""))+'</div>').join(""):'<p class="empty">This account has no automatically bookable plan under the approved reading.</p>'));
}
function readSettings(){
 const dc=data.settings?.day_count||"exclude_first";
 modal("Review rule settings",'<p class="muted">Approve a test date and counting convention for this event. Both officer identities are recorded.</p><div class="form-row"><label>Eligibility test date<select class="select" id="reading">'+data.readings.map(r=>'<option value="'+esc(r.id)+'" '+(r.id===preview?'selected':'')+'>'+esc(r.label)+'</option>').join("")+'</select></label><label>Declaration day<select class="select" id="day-count"><option value="exclude_first">Exclude declaration day</option><option value="include_first" '+(dc==="include_first"?"selected":"")+'>Include declaration day</option></select></label></div>'+officers()+btn("reading","Approve settings","primary"));
}
function officers(){return '<div class="form-row"><label>Maker<input id="maker" value="M. Rao" maxlength="60"></label><label>Checker<input id="checker" value="S. Iyer" maxlength="60"></label></div>'}
function selected(){return wf().plans.find(x=>x.id===selectedPlan)}
function paint(){
 document.title=names[view]+" · CalamityOS";$("#crumb").textContent=names[view];document.querySelectorAll("[data-view]").forEach(x=>{if(x.dataset.view===view)x.setAttribute("aria-current","page");else x.removeAttribute("aria-current")});
 $("#content").innerHTML=({overview,rules,ledger}[view])()+'<footer class="page-foot"><span>MOCK CORE · SYNTHETIC BORROWERS · ILLUSTRATIVE SCENARIO</span><span>Demo date · '+date(wf().as_of)+'</span></footer>';
 if(view==="overview")terrain();if(view==="rules"){renderRegister();$("#search").oninput=e=>{search=e.target.value;page=0;renderRegister()};$("#filter").onchange=e=>{filter=e.target.value;page=0;renderRegister()};$("#flips").onchange=e=>{onlyChanges=e.target.checked;page=0;renderRegister()}}
}
function go(v){if(!names[v])return;view=v;location.hash=v;paint();scrollTo(0,0)}
function toast(x){const t=$("#toast");clearTimeout(toastTimer);t.textContent=x;t.className="visible";toastTimer=setTimeout(()=>t.className="",5500)}
async function send(action,inputs={}){
 if(busy)return;busy=true;const clicked=document.activeElement;if(clicked?.tagName==="BUTTON")clicked.disabled=true;
 try{const resp=await fetch("/api/action",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action,...inputs})});const res=await resp.json();if(!resp.ok||res.error)throw Error(res.error||"Action failed");
 data=res;if(action==="batch"&&wf().batch_result?.stopped_at)selectedPlan=wf().batch_result.stopped_at;if(action==="draft"){selectedPlan=wf().plans.find(x=>x.borrower_id===inputs.borrower_id&&x.status==="DRAFT")?.id||"";view="ledger";location.hash="ledger"}if(action==="reset"){selectedPlan="";preview=activeReading()}$("#detail").close();paint();toast(action==="batch"&&wf().batch_result?.stopped_at?"Batch stopped: "+wf().batch_result.remaining.length+" left unprocessed":action==="advance"?"Demo date advanced":human(action)+" recorded");
 }catch(e){const msg=e.message||"Request failed";if($("#detail").open){let note=$("#modal-error");if(!note){note=document.createElement("p");note.id="modal-error";note.className="inset red";note.setAttribute("role","alert");$("#detail-body").append(note)}note.textContent=msg}else toast(msg)}finally{busy=false;if(clicked?.isConnected)clicked.disabled=false}
}
document.addEventListener("click",e=>{
 const el=e.target.closest("[data-view],[data-do],[data-open-evidence]");if(!el)return;if(el.hasAttribute("data-open-evidence")){if($("#detail").open)$("#detail").close();return}if(el.dataset.view){go(el.dataset.view);return}
 const k=el.dataset.do,id=el.dataset.id,p=selected(),args={plan_id:selectedPlan};
 if(k==="approved-preview"){preview=activeReading();onlyChanges=false;page=0;paint();borrower($("#detail").dataset.borrower)}else if(k==="close")$("#detail").close();else if(k==="batch-tools")batchModal("book");else if(k==="batch-run")runBatch();else if(k==="sources")sources();else if(k==="rules")go("rules");else if(k==="preview"){preview=id;page=0;paint()}else if(k==="prev"||k==="next"){page+=k==="prev"?-1:1;renderRegister()}else if(k==="borrower")borrower(id);
 else if(k==="reading-approval")readSettings();else if(k==="reading")send("reading",{reading:$("#reading").value,day_count:$("#day-count").value,maker:$("#maker").value,checker:$("#checker").value});else if(k==="draft")send("draft",{borrower_id:id,option:el.dataset.option});else if(k==="existing-plan"){$("#detail").close();selectedPlan=id;go("ledger")}else if(k==="plan"){selectedPlan=id;paint()}
 else if(k==="approve-modal")modal("Approve relief plan",'<p class="muted">Record distinct maker and checker identities for '+esc(p.name)+'.</p>'+officers()+btn("approve","Approve plan","primary"));else if(k==="approve")send("approve",{...args,maker:$("#maker").value,checker:$("#checker").value});
 else if(["object","notify","reconcile"].includes(k))send(k,args);
 else if(k==="book-modal")modal("Book and verify",'<p class="muted">Confirm the approved plan on the mock lending core, then compare the returned schedule.</p><div class="form-row"><label>Core response<select class="select" id="fault"><option value="">Normal booking</option><option value="shifted_date">Inject shifted repayment date</option><option value="missing_event">Inject missing event</option><option value="wrong_amount">Inject wrong amount</option><option value="timeout_after_commit">Inject timeout after commit</option></select></label></div>'+btn("book","Confirm booking","primary"));else if(k==="book")send("book",{...args,fault:$("#fault").value});
 else if(k==="opt-modal")modal("Review borrower opt-out",'<p class="muted">Restore the original schedule and verify the reversal against the mock core.</p><div class="details-grid">'+field("Borrower",p.name)+field("Catch-up preview",p.catch_up!=null?money(p.catch_up):"See restored schedule")+field("Added provision",money(p.provision))+'</div>'+btn("opt_out","Confirm opt-out","primary"));else if(k==="opt_out")send(k,args);
 else if(k==="lineage"){const b=data.borrowers.find(x=>x.id===p.borrower_id),s=data.event.sources[0];modal("Borrower lineage",'<div class="source"><strong>'+esc(p.source_record?.source||"Reviewed AP committee brief")+'</strong><p>'+esc(p.source_excerpt||s.excerpt)+'</p></div>'+[["Rule version",p.rule_version||data.event.rule_version],["Rule maker",p.rule_maker],["Rule checker",p.rule_checker],["Outcome reasons",(p.reason_codes||[]).join(", ")],["Borrower",p.borrower_id],["Loan",p.facility_id],["Snapshot hash",p.snapshot_hash||b?.snapshot_hash],["Maker",p.maker],["Checker",p.checker],["Core transaction",p.txn_ref]].map(([l,v])=>v?'<div class="row"><span>'+l+'</span><span class="mono" style="overflow-wrap:anywhere;text-align:right">'+esc(v)+'</span></div>':"").join("")+wf().ledger.filter(x=>x.plan_id===p.id).map(x=>'<div class="ledger-event"><time>'+date(x.day)+'</time><div>'+esc(x.message)+'</div></div>').join(""))}
 else if(k==="date-tools")modal("Demo controls",'<p class="muted">The workspace uses a fixed simulation date. Advance it to close a notice window.</p><div class="form-row"><label>Days to advance<input id="advance" type="number" min="1" max="135" value="4"></label></div><p class="kicker">Booking kill switch · '+(wf().kill_switch?'Enabled':'Off')+'</p><div class="actions section-gap">'+btn("advance","Advance demo date","primary")+btn("kill_switch",wf().kill_switch?"Enable new bookings":"Pause new bookings")+btn("reset-modal","Reset workspace")+'</div>');else if(k==="advance")send("advance",{days:Number($("#advance").value)});else if(k==="reset-modal")modal("Reset demo workspace?",'<p class="muted">Restore the seeded scenario and replace all demo actions recorded during this run.</p><div class="actions section-gap">'+btn("reset","Reset demo","primary")+btn("close","Keep workspace")+'</div>');else if(k==="reset")send("reset");else if(k==="kill_switch")send(k,{enabled:!wf().kill_switch});
});
$("#detail").addEventListener("click",e=>{if(e.target===$("#detail")){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close()}});
window.addEventListener("hashchange",()=>{const v=location.hash.slice(1);if(data&&names[v]&&v!==view)go(v)});
window.addEventListener("resize",()=>{if(data&&view==="overview")terrain()});
document.querySelectorAll("[data-icon]").forEach(x=>x.outerHTML=icon(x.dataset.icon));
async function boot(){try{const response=await fetch("/api/dashboard");if(!response.ok)throw Error("HTTP "+response.status);data=await response.json();view=names[location.hash.slice(1)]?location.hash.slice(1):"overview";preview=activeReading();paint()}catch(e){$("#content").innerHTML='<section class="panel"><h2>Workspace unavailable</h2><p>'+esc(e.message)+'</p><button class="btn" onclick="location.reload()">Retry</button></section>';console.error(e)}}
boot();

function policyPanels(){return '<div class="cols">'+(data.policy_readings||[]).map(r=>'<section class="panel">'+cardhead(esc(r.title),esc(r.context))+'<div class="eyebrow">'+num(r.cohort)+' BORROWERS'+(r.illustrative?' · ILLUSTRATIVE':'')+'</div>'+r.options.map(x=>'<div class="row"><span>'+esc(x.label)+'<small style="display:block">'+num(x.affected_count)+' change vs. baseline</small></span><strong>'+shortMoney(x.provision)+'</strong></div>').join("")+'</section>').join("")+'</div>'}

function batchModal(operation) {
 const w=wf(), eligible=w.plans.filter(p=>operation==="approve"?p.status==="DRAFT":operation==="notify"?p.status==="APPROVED":p.status==="NOTIFIED"&&w.as_of>p.objection_deadline&&w.as_of<=p.deadline);
 const blocked=operation==="book"&&(w.paused||w.kill_switch);
 const result=w.batch_result;
 const rows=eligible.map(p=>'<label class="row"><span><input type="checkbox" name="batch-plan" value="'+esc(p.id)+'" checked> '+esc(p.name)+'</span><span class="mono">'+esc(p.id)+'</span></label>').join("");
 modal("Manage booking batch",'<div class="form-row"><label>Batch operation<select id="batch-op" class="select">'+[["approve","Approve plans"],["notify","Issue notices"],["book","Book and verify"]].map(([v,l])=>'<option value="'+v+'" '+(operation===v?"selected":"")+'>'+l+'</option>').join("")+'</select></label></div>'+
 (operation==="approve"?officers():"")+'<h3>Eligible plans</h3>'+(rows||'<p class="empty">No plans are ready for this operation.</p>')+
 (operation==="book"&&eligible.length?'<div class="form-row"><label>Core response<select id="batch-fault-plan" class="select"><option value="">Normal bookings</option>'+eligible.map(p=>'<option value="'+esc(p.id)+'">Shift repayment date on '+esc(p.id)+'</option>').join("")+'</select></label></div>':'')+
 (blocked?'<p class="inset red">New bookings are paused.</p>':'')+
 btn("batch-run",human(operation)+" selected plans","primary",!eligible.length||blocked?'disabled':'')+
 (result?.operation?'<div class="inset"><strong>Last batch · '+esc(human(result.operation))+'</strong><p>Processed '+esc(Array.isArray(result.processed)?result.processed.length:result.processed)+' · Remaining '+esc(Array.isArray(result.remaining)?result.remaining.length:result.remaining)+(result.stopped_at?' · Stopped at '+esc(result.stopped_at):'')+'</p></div>':''));
 $("#batch-op").onchange=e=>batchModal(e.target.value);
}
function runBatch(){const operation=$("#batch-op").value,plan_ids=[...document.querySelectorAll('[name="batch-plan"]:checked')].map(x=>x.value),fault_plan_id=$("#batch-fault-plan")?.value;
 if(!plan_ids.length||(fault_plan_id&&!plan_ids.includes(fault_plan_id))){const div=$("#detail-body");let msg=$("#batch-error");if(!msg){msg=document.createElement("p");msg.id="batch-error";msg.className="inset red";msg.setAttribute("role","alert");div.append(msg)}msg.textContent="Select at least one plan and include the fault target if one is set.";return}
 send("batch",{operation,plan_ids,maker:$("#maker")?.value,checker:$("#checker")?.value,fault_plan_id,fault:fault_plan_id?"shifted_date":""});
}

