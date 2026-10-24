'use client';
import {useEffect,useState} from 'react';
import {ArrowRight,LoaderCircle,Mail,ShieldCheck,Sprout} from 'lucide-react';

export default function SignIn({configured,onSuccess}:{configured:boolean;onSuccess:()=>void}) {
  const [staffMode,setStaffMode]=useState(false);
  const [username,setUsername]=useState('');
  const [password,setPassword]=useState('');
  const [email,setEmail]=useState('');
  const [code,setCode]=useState('');
  const [sent,setSent]=useState(false);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [cooldown,setCooldown]=useState(0);
  useEffect(()=>{if(!cooldown)return;const timer=setTimeout(()=>setCooldown(c=>c-1),1000);return()=>clearTimeout(timer);},[cooldown]);
  async function submit(verify:boolean){
    if(busy)return;
    setBusy(true);setError('');
    try{
      const r=await fetch(staffMode?'/api/staff/login':'/api/auth/'+(verify?'verify':'send'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(staffMode?{username,password}:{email:email.trim().toLowerCase(),...(verify?{code}:{})})});
      const data=await r.json();
      if(!r.ok)throw new Error(typeof data.detail==='string'?data.detail:'Check your email address and six-digit code.');
      if(verify||staffMode)onSuccess();else{setEmail(data.email);setSent(true);setCode('');setCooldown(data.resend_after);}
    }catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  return <main className="auth-page"><a className="brand" href="/"><span className="brand-mark"><Sprout size={25}/></span><span>fixmyblock<span className="brand-period">.</span></span></a>
    <section className="auth-card"><span className="auth-icon">{sent?<Mail size={27}/>:<Sprout size={29}/>}</span><div className="eyebrow">NITK CAMPUS COMMUNITY</div><h1>{staffMode?'Welcome back, team.':sent?'Check your inbox.':'Your campus. Your voice.'}</h1><p>{staffMode?'Use the user ID and password provided by your administrator.':sent?<>Enter the six-digit code sent to <strong>{email}</strong>. It expires in 10 minutes.</>:'Sign in with your NITK email to report an issue and follow the repair. No password to remember.'}</p>
      <div className="login-tabs"><button className={!staffMode?"active":""} type="button" onClick={()=>{setStaffMode(false);setError('');}}>Student</button><button className={staffMode?"active":""} type="button" onClick={()=>{setStaffMode(true);setError('');}}>Maintenance / Admin</button></div>
      {!configured&&!staffMode&&<div className="notice" role="status">Email sign-in is being set up. The app owner needs to connect WorkOS before codes can be sent.</div>}
      <form onSubmit={e=>{e.preventDefault();submit(sent);}}>
        {staffMode?<><label htmlFor="staff-username">User ID</label><input id="staff-username" autoComplete="username" required maxLength={64} value={username} onChange={e=>setUsername(e.target.value)} disabled={busy}/><label htmlFor="staff-password">Password</label><input id="staff-password" type="password" autoComplete="current-password" required maxLength={200} value={password} onChange={e=>setPassword(e.target.value)} disabled={busy}/></>:sent?<><label htmlFor="login-code">Six-digit code</label><input autoFocus id="login-code" className="code-input" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,''))} placeholder="000000" disabled={busy}/></>:<><label htmlFor="login-email">NITK email address</label><input autoFocus id="login-email" type="email" autoComplete="email" required maxLength={254} pattern="[^@\s]+@nitk\.edu\.in" placeholder="yourname@nitk.edu.in" value={email} onChange={e=>setEmail(e.target.value)} disabled={busy}/><small>Only @nitk.edu.in email addresses are accepted.</small></>}
        {error&&<div className="error" role="alert">{error}</div>}
        <button className="primary" disabled={busy||(!staffMode&&(!configured||(sent&&code.length!==6)))} type="submit">{busy?<LoaderCircle size={18} className="spin"/>:null}{busy?'Please wait…':staffMode?'Sign in to dashboard':sent?'Verify and sign in':'Send me a code'}{!busy&&<ArrowRight size={17}/>}</button>
      </form>
      {sent&&!staffMode&&<div className="auth-actions"><button disabled={busy||cooldown>0} onClick={()=>submit(false)}>{cooldown?`Resend in ${cooldown}s`:'Resend code'}</button><button disabled={busy} onClick={()=>{setSent(false);setCode('');setError('');}}>Use another email</button></div>}
      <div className="privacy-note"><ShieldCheck size={16}/><span>{staffMode?'Team access is managed by your administrator.':'Secure email verification powered by WorkOS.'}</span></div>
    </section><p className="auth-footer">Independent student prototype · Not an official NITK service</p></main>;
}
