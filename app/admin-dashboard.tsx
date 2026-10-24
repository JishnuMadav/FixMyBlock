'use client';
import {useEffect,useState} from 'react';
import {KeyRound,Plus,ShieldCheck,Users,Wrench} from 'lucide-react';

type Account={id:string;username:string;name:string;role:string;team:string;active:number;must_change:number};
type Summary={teams:string[];counts:{team:string;status:string;count:number}[];audit:{id:number;action:string;detail:string;created_at:string}[]};
type Credential={username:string;temporary_password:string;team:string};
async function call<T>(path:string,body?:unknown):Promise<T>{
  const r=await fetch('/api/staff'+path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined});
  const d=await r.json();if(r.status===401)window.dispatchEvent(new Event('fmb-session-expired'));if(!r.ok)throw new Error(typeof d.detail==='string'?d.detail:'Check the account details and try again.');return d;
}

export function ChangePassword({onSuccess}:{onSuccess:()=>void}){
  const [current,setCurrent]=useState('');const [password,setPassword]=useState('');const [confirm,setConfirm]=useState('');const [error,setError]=useState('');const [busy,setBusy]=useState(false);
  return <main className="auth-page"><section className="auth-card"><span className="auth-icon"><KeyRound/></span><div className="eyebrow">SECURE YOUR ACCOUNT</div><h1>Make it yours.</h1><p>Replace your temporary password before opening your dashboard.</p><form onSubmit={async e=>{e.preventDefault();if(password!==confirm){setError('The new passwords do not match.');return;}setBusy(true);setError('');try{await call('/password',{current_password:current,new_password:password});onSuccess();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>
    <label htmlFor="old-password">Temporary or current password</label><input id="old-password" type="password" autoComplete="current-password" required maxLength={200} value={current} onChange={e=>setCurrent(e.target.value)}/>
    <label htmlFor="new-password">New password</label><input id="new-password" type="password" autoComplete="new-password" required minLength={12} maxLength={200} value={password} onChange={e=>setPassword(e.target.value)}/><small>Use at least 12 characters.</small>
    <label htmlFor="confirm-password">Confirm new password</label><input id="confirm-password" type="password" autoComplete="new-password" required minLength={12} maxLength={200} value={confirm} onChange={e=>setConfirm(e.target.value)}/>
    {error&&<div className="error" role="alert">{error}</div>}<button className="primary" disabled={busy}>{busy?'Saving…':'Save password and continue'}</button></form><button className="text-button" onClick={async()=>{await fetch('/api/auth/logout',{method:'POST'});onSuccess();}}>Sign out</button></section></main>;
}

export default function AdminDashboard({onQueue}:{onQueue:()=>void}){
  const [accounts,setAccounts]=useState<Account[]>([]);const [summary,setSummary]=useState<Summary|null>(null);const [error,setError]=useState('');const [busy,setBusy]=useState(false);const [username,setUsername]=useState('');const [name,setName]=useState('');const [team,setTeam]=useState('Electrical team');const [credential,setCredential]=useState<Credential|null>(null);
  async function refresh(){const [a,s]=await Promise.all([call<Account[]>('/accounts'),call<Summary>('/summary')]);setAccounts(a);setSummary(s);}
  useEffect(()=>{refresh().catch(e=>setError(e.message));},[]);
  async function change(id:string,action:string){setBusy(true);setError('');setCredential(null);try{const d=await call<Credential>('/accounts/'+id,{action});if(d.temporary_password)setCredential(d);await refresh();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  return <div className="admin-dashboard">
    {error&&<div className="error" role="alert">{error}<button onClick={()=>refresh().then(()=>setError('')).catch(e=>setError(e.message))}>Retry</button></div>}
    <div className="team-summary-grid">{summary?.teams.map(t=>{const rows=summary.counts.filter(c=>c.team===t);return <button className="team-summary-card" key={t} onClick={onQueue}><Wrench size={20}/><strong>{t}</strong><span>{rows.filter(r=>r.status!=='Resolved').reduce((n,r)=>n+r.count,0)} open reports</span><small>{rows.find(r=>r.status==='Resolved')?.count||0} resolved · View work queue →</small></button>;})}</div>
    {credential&&<section className="credential-card" role="status"><KeyRound size={22}/><div><h2>Account credentials — shown once</h2><p>Share these privately with the team member. They must change the password at first sign-in.</p><label>User ID<input readOnly value={credential.username}/></label><label>Temporary password<input readOnly value={credential.temporary_password}/></label><small>{credential.team}</small><button className="secondary" onClick={()=>setCredential(null)}>I have saved these credentials</button></div></section>}
    <div className="admin-columns"><section className="admin-panel"><h2><Plus size={19}/>Create a team account</h2><p>Choose the team. We generate a secure temporary password.</p><form className="admin-form" onSubmit={async e=>{e.preventDefault();setBusy(true);setError('');setCredential(null);try{setCredential(await call<Credential>('/accounts',{username,name,team}));setUsername('');setName('');await refresh();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>
      <label htmlFor="staff-name">Team member / account name</label><input id="staff-name" required minLength={2} maxLength={80} value={name} onChange={e=>setName(e.target.value)} placeholder="Electrical desk"/>
      <label htmlFor="staff-id">User ID</label><input id="staff-id" required pattern="[a-zA-Z0-9][a-zA-Z0-9._-]{2,39}" maxLength={40} value={username} onChange={e=>setUsername(e.target.value)} placeholder="electrical.desk"/><small>3–40 letters, numbers, dots, underscores or hyphens.</small>
      <label htmlFor="staff-team">Assigned team</label><select id="staff-team" value={team} onChange={e=>setTeam(e.target.value)}>{(summary?.teams||['Electrical team','Sanitation team','Grounds team','Plumbing team']).map(t=><option key={t}>{t}</option>)}</select><button className="primary" disabled={busy}><Plus size={16}/>{busy?'Please wait…':'Generate account'}</button></form></section>
      <section className="admin-panel"><h2><Users size={19}/>Team accounts</h2><p>Resetting a password or disabling an account signs it out immediately.</p><div className="account-list">{accounts.filter(a=>a.role==='team').map(a=><article key={a.id}><div><strong>{a.name}</strong><span>{a.username} · {a.team}</span><small>{!a.active?'Disabled':a.must_change?'Awaiting password change':'Active'}</small></div><div className="account-actions"><button disabled={busy} onClick={()=>change(a.id,'reset')}>Reset password</button><button disabled={busy} onClick={()=>change(a.id,a.active?'disable':'enable')}>{a.active?'Disable':'Enable'}</button></div></article>)}{!accounts.some(a=>a.role==='team')&&<p>No team accounts yet. Create the first one here.</p>}</div></section></div>
    <section className="admin-panel"><h2><ShieldCheck size={19}/>Admin activity</h2><div className="admin-audit">{summary?.audit.map(a=><div key={a.id}><strong>{a.action}</strong><span>{a.detail}</span><small>{new Date(a.created_at).toLocaleString('en-IN')}</small></div>)}{!summary?.audit.length&&<p>Account activity will appear here.</p>}</div></section>
  </div>;
}
