'use client';

import { useEffect, useRef, useState } from 'react';
import {CampusMap,LocationPicker,Pin,googleLink,pinName} from './campus-map';
import campus from '../shared/campus.json';
import SignIn from './sign-in';
import AdminDashboard,{ChangePassword} from './admin-dashboard';
type Photo={id:string;url:string;analysis:{is_issue:boolean;category:string|null;summary:string;uncertainty:string;mode:string}};
type Config = {mode:string;demo:boolean;hours:number;auth_required:boolean;auth_configured:boolean;user:{user_id:string;email:string;name:string;role:string;team:string|null;must_change:boolean}|null;operator:boolean};
import { ArrowUp, ArrowUpRight, ArrowRight, Check, CheckCheck, ChevronDown, ChevronRight, CircleHelp, Clock3, ClipboardList, Compass, Leaf, Lightbulb, LoaderCircle, MapPin, MessageSquare, Plus, Search, ShieldCheck, Sparkles, Sprout, Trash2, Wrench, X, Droplets, Route, RotateCcw, ExternalLink, Camera, Shield } from 'lucide-react';

type Ticket = { photos:Photo[]; latitude:number|null; longitude:number|null; location_detail:string|null; id:number; reference:string; title:string; description:string; category:string; location:string; team:string; status:string; reports:number; mine:boolean; overdue:boolean; sample:number; created_at:string; due_at:string; followup:string|null; proposal:string|null; events:{id:number;action:string;detail:string;actor:string;created_at:string}[] };
type Choice = {label:string;message?:string;action?:'submit'|'link'|'separate'};
type ChatResult = {message:string;choices:Choice[];trace:{label:string;detail:string}[];phase:string;mode:string;draft:{title:string;category:string;location:string;team:string;pin?:Pin;photo_id?:string;photo_analysis?:Photo["analysis"]};ticket:Ticket|null};
type Message = {role:'user'|'assistant';text:string;result?:ChatResult};
type View = 'report'|'mine'|'campus'|'maintenance'|'admin';
const categories = [{name:'Lighting',icon:Lightbulb,text:'A streetlight isn’t working',class:'amber'},{name:'Waste & litter',icon:Trash2,text:'There’s rubbish piling up',class:'sage'},{name:'Roads & paths',icon:Route,text:'There is a pothole on the road',class:'terracotta'},{name:'Drainage',icon:Droplets,text:'A drain is blocked',class:'blue'}];
const iconFor = (category:string) => category==='Lighting'?Lightbulb:category==='Waste'?Trash2:category==='Roads'?Route:Droplets;
const statusClass=(status:string)=> status==='Resolved'?'resolved':status==='In progress'?'progress':status==='Awaiting verification'?'verification':'assigned';
const date=(value:string)=>new Date(value).toLocaleDateString('en-IN',{day:'numeric',month:'short'});
async function api<T>(path:string, method='GET', body?:unknown):Promise<T> {
  const r=await fetch('/api'+path,{method,headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined});
  const data=await r.json();
  if(r.status===401)window.dispatchEvent(new Event('fmb-session-expired'));
  if(!r.ok) throw new Error(typeof data.detail==='string'?data.detail:'Something went wrong. Please try again.');
  return data;
}

export default function Home(){
  const [view,setView]=useState<View>('report');
  const [photo,setPhoto]=useState<Photo|null>(null);
  const photoInput=useRef<HTMLInputElement>(null);
  const [pin,setPin]=useState<Pin|null>(null);
  const [pickerOpen,setPickerOpen]=useState(false);
  const [tickets,setTickets]=useState<Ticket[]>([]);
  const [config,setConfig]=useState<Config|null>(null);
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const [text,setText]=useState('');
  const [messages,setMessages]=useState<Message[]>([]);
  const [conversation,setConversation]=useState('');
  const [selected,setSelected]=useState<Ticket|null>(null);
  const [note,setNote]=useState('');
  const [query,setQuery]=useState('');
  const [filter,setFilter]=useState('All reports');
  const [help,setHelp]=useState(false);
  const [notice,setNotice]=useState('');
  const [pending,setPending]=useState<{message:string;action?:Choice['action'];request_id:string;pin?:Pin|null;photo_id?:string|null}|null>(null);
  const chatEnd=useRef<HTMLDivElement>(null);
  const dialog=useRef<HTMLDialogElement>(null);
  const textarea=useRef<HTMLTextAreaElement>(null);
  const active=tickets.filter(t=>t.status!=='Resolved');
  const mine=tickets.filter(t=>t.mine);
  const latest=messages.at(-1)?.result;
  const load=async()=>{ const data=await api<Ticket[]>('/tickets');setTickets(data);return data; };
  useEffect(()=>{
    setConversation(crypto.randomUUID());
    api<Config>('/bootstrap').then(c=>{setConfig(c);if(c.user?.role==='admin')setView('admin');else if(c.user?.role==='team')setView('maintenance');if((!c.auth_required||c.user)&&!c.user?.must_change)return load();}).catch(e=>setError(e.message));
    const expire=()=>{setConfig(c=>c?{...c,user:null}:c);setTickets([]);setMessages([]);setSelected(null);setHelp(false);};
    window.addEventListener('fmb-session-expired',expire);
    return()=>window.removeEventListener('fmb-session-expired',expire);
  },[]);
  useEffect(()=>{if(!config||(config.auth_required&&!config.user)||config.user?.must_change)return;const interval=setInterval(()=>{load().catch(()=>{});},12000);return()=>clearInterval(interval);},[config]);
  useEffect(()=>{if(messages.length)chatEnd.current?.scrollIntoView({behavior:'smooth',block:'nearest'});},[messages,busy]);
  useEffect(()=>{if(selected||help){dialog.current?.showModal();}else{dialog.current?.close();} setNote('');},[selected?.id,help]);

  async function send(message:string,action?:Choice['action'],retry=false,newPin?:Pin,newPhoto?:Photo|null){
    if(busy||!config||(!message.trim()&&!action))return;
    setBusy(true);setError('');setText('');
    const request=retry&&pending?pending:{message,action,request_id:crypto.randomUUID(),pin:newPin||pin,photo_id:(newPhoto===undefined?photo:newPhoto)?.id||null};
    setPending(request);
    if(!retry)setMessages(prev=>[...prev,{role:'user',text:message}]);
    try{
      const result=await api<ChatResult>('/chat','POST',{...request,conversation_id:conversation});
      setMessages(prev=>[...prev,{role:'assistant',text:result.message,result}]);
      setPending(null);await load();
    }catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  async function uploadPhoto(file:File){
    if(busy)return;
    if(file.size>5*1024*1024){setError('Choose a photo smaller than 5 MB.');return;}
    setBusy(true);setError('');
    let uploaded:Photo|null=null;
    try{const r=await fetch('/api/photos',{method:'POST',headers:{'Content-Type':file.type},body:file});const d=await r.json();if(r.status===401)window.dispatchEvent(new Event('fmb-session-expired'));if(!r.ok)throw new Error(typeof d.detail==='string'?d.detail:'Photo upload failed.');uploaded=d;setPhoto(d);}catch(e){setError((e as Error).message);}finally{setBusy(false);if(photoInput.current)photoInput.current.value='';}
    // Changing evidence invalidates the old review; the next message rechecks it.
    if(uploaded&&messages.length){setMessages(prev=>[...prev,{role:'assistant',text:'Photo added. Send a short description below to review the updated report.'}]);setPending(null);}
  }
  function fresh(){setPhoto(null);setPin(null);setMessages([]);setText('');setConversation(crypto.randomUUID());setError('');setPending(null);setView('report');setTimeout(()=>textarea.current?.focus(),50);}
  function savePin(p:Pin){setPin(p);setPickerOpen(false);if(messages.length>0)send('Use this location: '+pinName(p)+(p.detail?' — '+p.detail:''),undefined,false,p);}
  function chooseReply(c:Choice){const l=campus.landmarks.find(l=>l.name===c.message);if(l){const p={lat:l.lat,lng:l.lng,detail:''};setPin(p);send(c.message||c.label,c.action,false,p);}else send(c.message||c.label,c.action);}
  async function navigate(v:View){
    setError('');
    if(v==='maintenance'){
      try{await api('/demo/operator','POST');}catch(e){setError((e as Error).message);return;}
    }
    setView(v);setFilter('All reports');setQuery('');
  }
  async function mutate(path:string,method='POST',body?:unknown){
    setBusy(true);setError('');
    try{await api(path,method,body);const data=await load();if(selected)setSelected(data.find(t=>t.id===selected.id)||null);setNote('');}
    catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  async function advance(){
    setBusy(true);setError('');
    try{const r=await api<{flagged:number;hours:number}>('/demo/advance','POST');setConfig(c=>c?{...c,hours:r.hours}:c);setNotice(`Demo clock advanced 24 hours. ${r.flagged} ticket${r.flagged===1?'':'s'} flagged for follow-up.`);await load();}catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  function openTicket(t:Ticket){setSelected(t);setError('');}
  const filtered=(view==='mine'?mine:tickets).filter(t=>(filter==='All reports'||(filter==='Needs attention'?t.overdue||!!t.followup:t.status===filter))&&`${t.title} ${t.reference} ${t.location}`.toLowerCase().includes(query.toLowerCase()));

  if(!config)return <main className="auth-page"><p>{error||"Loading FixMyBlock…"}</p>{error&&<button className="primary" onClick={()=>window.location.reload()}>Retry</button>}</main>;
  if(config.user?.must_change)return <ChangePassword onSuccess={()=>window.location.reload()}/>;
  if(config.auth_required&&!config.user)return <SignIn configured={config.auth_configured} onSuccess={()=>window.location.reload()}/>;

  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="/" aria-label="FixMyBlock home"><span className="brand-mark"><Sprout size={25}/></span><span>fixmyblock<span className="brand-period">.</span></span></a>
      <div className="workspace"><span className="workspace-icon"><MapPin size={18}/></span><div><strong>NITK Surathkal</strong><small>Independent campus demo</small></div><span className="workspace-dot"/></div>
      <div className="nav-label">{config.user?.role==='student'||!config.user?'YOUR NEIGHBORHOOD':'WORKSPACE'}</div>
      <nav aria-label="Main navigation">
        {(config.user?.role==='admin'?[{key:'admin',icon:Shield,label:'Admin dashboard'}]:config.user?.role==='team'?[]:[{key:'report',icon:Plus,label:'Report an issue'},{key:'mine',icon:ClipboardList,label:'My reports'},{key:'campus',icon:Compass,label:'Around campus'}]).map(item=><button key={item.key} className={`nav-item ${view===item.key?'active':''}`} onClick={()=>navigate(item.key as View)}><item.icon size={19}/>{item.label}{item.key==='mine'&&mine.length>0&&<span className="nav-count">{mine.length}</span>}</button>)}
        {config.operator&&<><div className="nav-divider"/><div className="nav-label">FOR MAINTENANCE</div>
        <button className={`nav-item ${view==='maintenance'?'active':''}`} onClick={()=>navigate('maintenance')}><Wrench size={18}/>{config.user?.role==='team'?'Team dashboard':'Work queue'}</button></>}
      </nav>
      <div className="sidebar-bottom"><div className="care-card"><Leaf size={22}/><strong>Small reports.<br/>Better places.</strong><p>A little care goes a long way for the place we share.</p><div className="care-line"/></div>
      <button className="help-button" onClick={()=>setHelp(true)}><CircleHelp size={18}/>How it works<ArrowUpRight size={15}/></button>
      <div className="profile"><span className="avatar">Y</span><div><strong>{config.user?.name||config.user?.email||"You, a good neighbor"}</strong><small>{config.user?.role==='team'?config.user.team:config.user?.role==='admin'?'Administrator':config.user?"Verified NITK email":"Local demo session"}</small></div></div>{config.user&&<button className="help-button" onClick={async()=>{try{await api("/auth/logout","POST");window.location.reload();}catch(e){setError((e as Error).message);}}}>Sign out<ArrowUpRight size={15}/></button>}</div>
    </aside>

    <main className="main">
      <header className="topbar"><div className="breadcrumb">Your neighborhood<ChevronRight size={13}/><strong>{view==='report'?'Report an issue':view==='mine'?'My reports':view==='campus'?'Around campus':view==='admin'?'Admin dashboard':config.user?.team||'Work queue'}</strong></div><span className="campus-badge"><span className="live-dot"/>NITK campus demo</span></header>
      <div className="page-content">
        <div className="page-heading"><div><div className="eyebrow"><span/> A LITTLE CARE. A BETTER CAMPUS.</div><h1>{view==='report'?<>A better block<br className="mobile-break"/> starts with you.</>:view==='mine'?'Your reports, all in one place.':view==='campus'?'Good things happen together.':view==='admin'?'A campus that works together.':config.user?.team||'Campus work queue'}</h1><p>{view==='report'?'Something needs a fix? Tell us what’s happening. We’ll help with the next step.':view==='mine'?'Follow the progress of the issues you’ve helped bring to light.':view==='campus'?'See what’s being cared for in your neighborhood.':view==='admin'?'Manage team access and see how repairs are progressing.':'Your assigned reports, next steps, and repair updates.'}</p></div>{view!=='report'&&(!config.user||config.user.role==='student')&&<button className="primary compact" onClick={fresh}><Plus size={17}/>New report</button>}</div>
        {error&&!selected&&!help&&<div className="error" role="alert">{error}{pending&&<button onClick={()=>send(pending.message,pending.action,true)}>Retry safely</button>}</div>}
        {notice&&<div className="notice" role="status">{notice}<button aria-label="Dismiss notification" onClick={()=>setNotice('')}><X size={15}/></button></div>}

        {view==='admin'?<AdminDashboard onQueue={()=>navigate('maintenance')}/>:view==='report'?<div className="report-grid">
          <section className="report-column"><div className="location-bar"><span className="location-bar-icon"><MapPin size={20}/></span><div><strong>{pin?pinName(pin):'Where on campus?'}</strong><small>{pin?(pin.detail||`${pin.lat.toFixed(5)}, ${pin.lng.toFixed(5)}`):'Add a pin for accurate routing and nearby matches.'}</small></div><button disabled={busy||latest?.phase==='done'} onClick={()=>setPickerOpen(true)}>{pin?'Change pin':'Choose location'}<ArrowUpRight size={14}/></button></div>
            <section className="photo-panel"><div className="photo-panel-top"><div><strong>Add a photo <span>Optional</span></strong><small>A photo can help explain the problem. You can report without one.</small></div><button className="secondary" disabled={busy||latest?.phase==='done'} onClick={()=>photoInput.current?.click()}><Camera size={17}/>{photo?'Replace photo':'Add photo'}</button><input ref={photoInput} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={e=>{const f=e.target.files?.[0];if(f)uploadPhoto(f);}}/></div><p className="photo-disclosure">JPEG, PNG or WebP · Up to 5 MB. Uploaded photos are sent to Gemini for analysis; avoid faces and personal information.</p>{photo&&<div className="photo-preview"><img src={photo.url} alt="Your attached maintenance photo"/><div><strong>{photo.analysis.mode==='gemini'?'AI photo observation':'Photo attached'}</strong><p>{photo.analysis.summary}</p><small>{photo.analysis.uncertainty}</small><div className="action-row"><button className="text-button" disabled={busy||latest?.phase==='done'} onClick={()=>send('Please review the maintenance issue in this photo.')}>Review this photo</button><button className="text-button" disabled={busy||latest?.phase==='done'} onClick={()=>{setPhoto(null);if(messages.length){setMessages(prev=>[...prev,{role:'assistant',text:'Photo removed. Send a description to review the report without it.'}]);setPending(null);}}}>Remove</button></div></div></div>}</section>
            <div className="chat-card">
              <div className="card-top"><div className="assistant-avatar"><Sparkles size={20}/></div><div><h2>Your neighborhood assistant</h2><span className="assistant-status"><span className="live-dot"/>{config?.mode==='gemini'?'Gemini configured · here to help':'Guided demo · no AI model connected'}</span></div>{messages.length>0&&<button className="icon-button" title="Start a new report" aria-label="Start a new report" onClick={fresh} disabled={busy}><Plus size={20}/></button>}</div>
              {messages.length===0?<div className="welcome"><span className="welcome-tag">LET’S MAKE IT BETTER</span><h2>What needs a little attention?</h2><p>A broken light. An overflowing bin. A rough patch on your route.<br/>Describe it in your own words — we’ll take it from there.</p><div className="suggestions">{categories.map(c=><button key={c.name} onClick={()=>send(c.text)} disabled={busy||!config}><span className={`category-icon ${c.class}`}><c.icon size={20}/></span><span>{c.name}</span><ArrowUpRight size={16}/></button>)}</div><div className="privacy-note"><ShieldCheck size={15}/><span>You’ll review the details before a report is submitted.</span></div></div>:<div className="conversation" aria-live="polite">{messages.map((m,i)=><div key={i} className={`message ${m.role}`}>
                {m.role==='assistant'&&<span className="message-avatar"><Sparkles size={15}/></span>}<div className="message-content"><div className="bubble">{m.text}</div>
                {m.result&&<>
                  {m.result.phase==='review'&&<div className="draft-card"><span className="eyebrow">YOUR REPORT · READY TO REVIEW</span><h3>{m.result.draft.title}</h3><p><MapPin size={14}/>{m.result.draft.location}</p><p><Wrench size={14}/>{m.result.draft.team}</p>{m.result.draft.photo_analysis&&<div className="draft-photo"><Camera size={14}/><span>Photo attached · {m.result.draft.photo_analysis.summary}</span></div>}{m.result.draft.pin&&<p><MapPin size={14}/>{m.result.draft.pin.lat.toFixed(6)}, {m.result.draft.pin.lng.toFixed(6)}{m.result.draft.pin.detail&&` · ${m.result.draft.pin.detail}`}</p>}</div>}
                  {m.result.ticket&&<button className="ticket-success" onClick={()=>openTicket(tickets.find(t=>t.id===m.result!.ticket!.id)||m.result!.ticket!)}><span><CheckCheck size={20}/><strong>{m.result.ticket.reference}</strong> · {m.result.ticket.status}</span><ArrowUpRight size={17}/></button>}
                  {m.result.trace.length>0&&<details className="trace"><summary><CheckCheck size={13}/>What happened<ChevronDown size={13}/></summary><ul>{m.result.trace.map((step,j)=><li key={j}><Check size={12}/><div><strong>{step.label}</strong><span>{step.detail}</span></div></li>)}</ul></details>}
                  {i===messages.length-1&&m.result.choices.length>0&&<div className="choices">{m.result.choices.map(c=><button disabled={busy} key={c.label} className={c.action==='submit'?'submit-choice':''} onClick={()=>chooseReply(c)}>{c.action==='submit'&&<Check size={14}/>} {c.label}</button>)}</div>}
                </>}</div></div>)}{busy&&<div className="thinking"><LoaderCircle size={15} className="spin"/>Checking the next step…</div>}<div ref={chatEnd}/></div>}
              {latest?.phase==='done'?<div className="done-footer"><span><Check size={16}/>Thanks for looking out for your neighborhood.</span><button onClick={fresh}>Report another issue<ArrowRight size={15}/></button></div>:<form className="composer" onSubmit={e=>{e.preventDefault();send(text);}}><textarea ref={textarea} aria-label="Describe the issue" placeholder={messages.length?'Add a detail or answer the question…':'Tell us what’s happening and where…'} value={text} maxLength={2000} onChange={e=>setText(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send(text);}}} disabled={busy||!config}/><div className="composer-bottom"><span><MapPin size={14}/>{pin?'Map pin attached':'Add a campus pin above'}</span><button type="submit" className="send" disabled={busy||!text.trim()||!config} aria-label="Send message">{busy?<LoaderCircle size={18} className="spin"/>:<ArrowUp size={20}/>}</button></div></form>}
            </div>
            <div className="steps"><div><span>01</span><strong>Tell us about it</strong><p>A few words are all it takes.</p></div><div><span>02</span><strong>We find the right team</strong><p>And check for existing reports.</p></div><div><span>03</span><strong>Follow the progress</strong><p>Until things are better.</p></div></div>
          </section>
          <aside className="neighborhood-column"><div className="neighborhood-card"><div className="section-heading"><h2>Around your campus</h2><Compass size={18}/></div><CampusMap tickets={tickets} onTicket={id=>{const t=tickets.find(t=>t.id===id);if(t)openTicket(t);}}/><button className="text-button map-report-link" disabled={busy||latest?.phase==='done'} onClick={()=>setPickerOpen(true)}><MapPin size={14}/>Choose a report location</button><div className="map-stats"><div><strong>{active.length.toString().padStart(2,'0')}</strong><span>Being cared for</span></div><div><strong>{tickets.filter(t=>t.status==='Resolved').length.toString().padStart(2,'0')}</strong><span>Marked resolved</span></div></div><div className="mini-divider"/><div className="recent-label">IN THE NEIGHBORHOOD<span>Sample + live reports</span></div><div className="mini-tickets">{active.slice(0,3).map(t=>{const Icon=iconFor(t.category);return <button key={t.id} onClick={()=>openTicket(t)}><span className={`mini-icon ${t.category==='Lighting'?'amber':t.category==='Waste'?'sage':'terracotta'}`}><Icon size={17}/></span><div><strong>{t.title}</strong><span>{t.location} · <em>{t.status}</em></span></div><ChevronRight size={15}/></button>})}</div><button className="text-button see-all" onClick={()=>navigate('campus')}>See all neighborhood reports<ArrowRight size={15}/></button></div><div className="kindness-note"><span><Sprout size={22}/></span><p>You don’t have to fix it yourself.<br/><strong>Noticing is a good place to start.</strong></p></div></aside>
        </div>:<>
          <div className="campus-demo-banner"><MapPin size={16}/><span><strong>NITK campus demo.</strong> Independent student prototype. Sample incidents and maintenance teams are fictional.</span></div>{(view==='campus'||view==='maintenance')&&<section className="campus-overview"><div className="section-heading"><h2>Reports across NITK</h2><span>{filtered.filter(t=>t.latitude!=null).length} mapped · {filtered.filter(t=>t.latitude==null).length} without a pin</span></div><CampusMap large tickets={filtered} onTicket={id=>{const t=tickets.find(t=>t.id===id);if(t)openTicket(t);}}/><div className="map-legend"><span><i/>Assigned</span><span><i className="legend-progress"/>In progress</span><span><i className="legend-resolved"/>Resolved</span><a href="https://www.openstreetmap.org/fixthemap" target="_blank" rel="noreferrer">Report a map issue</a></div></section>}<div className="stat-grid">{[{label:view==='mine'?'Your reports':'Total reports',value:view==='mine'?mine.length:tickets.length,icon:ClipboardList},{label:'In progress',value:(view==='mine'?mine:tickets).filter(t=>t.status==='In progress').length,icon:Wrench},{label:'Awaiting confirmation',value:(view==='mine'?mine:tickets).filter(t=>t.status==='Awaiting verification').length,icon:MessageSquare},{label:'Resolved',value:(view==='mine'?mine:tickets).filter(t=>t.status==='Resolved').length,icon:CheckCheck}].map(s=><div className="stat" key={s.label}><div><span>{s.label}</span><strong>{s.value.toString().padStart(2,'0')}</strong></div><s.icon size={22}/></div>)}</div>
          {view==='maintenance'&&<div className="operator-note"><div><Wrench size={18}/><span><strong>{config.user?.team||'Maintenance workspace'}</strong> — update assigned jobs and request resident verification.</span></div>{(!config.user||config.user.role==='admin')&&<button disabled={busy} onClick={advance}><Clock3 size={15}/>Advance demo time +24h</button>}</div>}
          <section className="reports-panel"><div className="table-toolbar"><div className="filters">{['All reports','In progress',view==='maintenance'?'Needs attention':'Resolved'].map(f=><button key={f} className={filter===f?'selected':''} onClick={()=>setFilter(f)}>{f}</button>)}</div><label className="search"><Search size={16}/><input aria-label="Search reports" placeholder="Search reports…" value={query} onChange={e=>setQuery(e.target.value)}/></label></div>
          {filtered.length===0?<div className="empty-state"><span><Sprout size={32}/></span><h2>{view==='mine'&&!mine.length?'Your first report can make a difference.':'No reports match your search.'}</h2><p>{view==='mine'&&!mine.length?'When you report an issue, its progress will appear here.':'Try another location, reference, or filter.'}</p>{view==='mine'&&!mine.length&&<button className="primary" onClick={fresh}><Plus size={16}/>Report an issue</button>}</div>:<div className="table-scroll"><table><thead><tr><th>ISSUE</th><th>LOCATION</th><th>STATUS</th><th>{view==='maintenance'?'ASSIGNED TEAM':'REPORTED'}</th><th><span className="sr-only">Details</span></th></tr></thead><tbody>{filtered.map(t=>{const Icon=iconFor(t.category);return <tr key={t.id}><td><button className="row-title" onClick={()=>openTicket(t)}><span className="table-icon"><Icon size={20}/></span><span><strong>{t.title}</strong><small>{t.reference} · {t.category}{t.sample?' · Sample':''}{t.overdue?' · Follow-up due':''}</small></span></button></td><td><span className="location-cell"><MapPin size={13}/>{t.location}</span></td><td><span className={`status ${statusClass(t.status)}`}><i/>{t.status}</span></td><td>{view==='maintenance'?t.team:date(t.created_at)}</td><td><button className="icon-button" aria-label={`View ${t.reference}`} onClick={()=>openTicket(t)}><ArrowUpRight size={18}/></button></td></tr>})}</tbody></table></div>}
          <div className="table-footer"><span>{filtered.length} report{filtered.length!==1?'s':''}</span><span><ShieldCheck size={13}/>Every update has a history.</span></div></section>
        </>}
        <footer className="page-footer"><span>Made for the place we share.</span><span><span className="live-dot"/>{config?.mode==='gemini'?'Gemini + LangGraph':'Rules-based demo'} · NITK demo · Fictional sample incidents</span></footer>
      </div>
    </main>
    <LocationPicker open={pickerOpen} pin={pin} onClose={()=>setPickerOpen(false)} onSave={savePin}/><dialog ref={dialog} onCancel={()=>{setSelected(null);setHelp(false);}} onClick={e=>{if(e.target===dialog.current){setSelected(null);setHelp(false);}}}>
      <div className="dialog-inner"><button className="dialog-close icon-button" aria-label="Close details" onClick={()=>{setSelected(null);setHelp(false);}}><X size={21}/></button>
      {help?<><div className="assistant-avatar"><Sprout size={24}/></div><h2>A little care, from start to finish.</h2><p>Describe an issue and its location. We’ll clarify missing details, look for related reports, and show you what will be submitted.</p><div className="help-steps"><p><strong>1. Review before sending.</strong> You confirm a new report or a possible duplicate.</p><p><strong>2. Follow the work.</strong> Open My reports to see maintenance updates.</p><p><strong>3. Confirm the repair.</strong> Let the team know whether the issue is really fixed.</p></div><div className="local-note">This is an independent NITK campus demo, not an official NITK service. Map landmarks come from OpenStreetMap and are approximate. Sample reports are fictional. Without a server-side Gemini key, the assistant uses basic demo rules. Do not enter private or emergency information.</div></>:selected&&<>
        <div className="detail-meta">{selected.reference}<span className={`status ${statusClass(selected.status)}`}><i/>{selected.status}</span></div><h2>{selected.title}</h2><div className="detail-location"><MapPin size={15}/>{selected.location}<span>·</span>{selected.category}{selected.sample>0&&<span className="sample-tag">Sample report</span>}</div><p className="description">{selected.description}</p>{selected.photos?.map(p=><div className="ticket-photo" key={p.id}><img src={p.url} alt="Resident-provided maintenance evidence"/><p><strong>AI observation:</strong> {p.analysis.summary}</p><small>{p.analysis.uncertainty}</small></div>)}{selected.latitude!=null&&selected.longitude!=null&&<div className="ticket-map-detail"><CampusMap pin={{lat:selected.latitude,lng:selected.longitude,detail:selected.location_detail||''}}/><p>{selected.location_detail||'Resident-selected pin'}</p><a href={googleLink(selected.latitude,selected.longitude)} target="_blank" rel="noreferrer"><ExternalLink size={13}/>Open location in Google Maps</a></div>}<div className="detail-stats"><div><span>Responsible team</span><strong>{selected.team}</strong></div><div><span>Resident reports</span><strong>{selected.reports}</strong></div></div>
        {error&&<div className="error" role="alert">{error}</div>}
        {selected.followup&&<div className="followup"><Clock3 size={17}/><div><strong>Follow-up needed</strong><p>{selected.followup}</p></div></div>}
        {selected.status==='Awaiting verification'&&selected.mine&&<div className="verify-card"><h3>Does everything look better?</h3><p>The team has reported the work complete. Your confirmation closes the loop.</p><div><button className="primary" disabled={busy} onClick={()=>mutate(`/tickets/${selected.id}/verify`,'POST',{fixed:true})}><Check size={15}/>Yes, it’s fixed</button><button className="secondary" disabled={busy} onClick={()=>mutate(`/tickets/${selected.id}/verify`,'POST',{fixed:false})}>Still needs work</button></div></div>}
        {view==='maintenance'&&selected.status!=='Resolved'&&<div className="maintenance-actions"><h3>Update this job</h3><label htmlFor="work-note">Maintenance note</label><textarea id="work-note" placeholder="What changed, or what is blocking the repair?" value={note} maxLength={1000} onChange={e=>setNote(e.target.value)}/><div className="action-row">{selected.status==='Assigned'&&<button disabled={busy||note.trim().length<5} className="primary" onClick={()=>mutate(`/tickets/${selected.id}`,'PATCH',{status:'In progress',note})}>Start work</button>}{selected.status==='In progress'&&<button disabled={busy||note.trim().length<5} className="primary" onClick={()=>mutate(`/tickets/${selected.id}`,'PATCH',{status:'Awaiting verification',note})}>Request repair verification</button>}<button disabled={busy||note.trim().length<5} className="secondary" onClick={()=>mutate(`/tickets/${selected.id}/followup`,'POST',{note})}><Sparkles size={14}/>Suggest next step</button></div><small>A note of at least 5 characters is required.</small>{selected.proposal&&(()=>{const p=JSON.parse(selected.proposal);return <div className="proposal"><span className="eyebrow">PROPOSED FOLLOW-UP</span><h4>{p.action}</h4><p>{p.reason}</p><button disabled={busy} className="primary" onClick={()=>mutate(`/tickets/${selected.id}/approve`)}>Approve for work queue<Check size={14}/></button></div>})()}</div>}
        <h3 className="history-title">Every step, in the open.</h3><div className="timeline">{selected.events.map(e=><div className="timeline-item" key={e.id}><span className="timeline-dot"><Check size={10}/></span><div><strong>{e.action}</strong><p>{e.detail}</p><small>{e.actor} · {date(e.created_at)}</small></div></div>)}</div>
      </>}</div>
    </dialog>
  </div>;
}
