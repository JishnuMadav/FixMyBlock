'use client';
import {useEffect,useState} from 'react';
import {ArrowRight,LoaderCircle,Mail,ShieldCheck,Sprout} from 'lucide-react';

export default function SignIn({configured,onSuccess}:{configured:boolean;onSuccess:()=>void}) {
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
      const r=await fetch('/api/auth/'+(verify?'verify':'send'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:email.trim().toLowerCase(),...(verify?{code}:{})})});
      const data=await r.json();
      if(!r.ok)throw new Error(typeof data.detail==='string'?data.detail:'Check your email address and six-digit code.');
      if(verify)onSuccess();else{setEmail(data.email);setSent(true);setCode('');setCooldown(data.resend_after);}
    }catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  return <main className="auth-page"><a className="brand" href="/"><span className="brand-mark"><Sprout size={25}/></span><span>fixmyblock<span className="brand-period">.</span></span></a>
    <section className="auth-card"><span className="auth-icon">{sent?<Mail size={27}/>:<Sprout size={29}/>}</span><div className="eyebrow">NITK CAMPUS COMMUNITY</div><h1>{sent?'Check your inbox.':'Your campus. Your voice.'}</h1><p>{sent?<>Enter the six-digit code sent to <strong>{email}</strong>. It expires in 10 minutes.</>:'Sign in with your NITK email to report an issue and follow the repair. No password to remember.'}</p>
      {!configured&&<div className="notice" role="status">Email sign-in is being set up. The app owner needs to connect WorkOS before codes can be sent.</div>}
      <form onSubmit={e=>{e.preventDefault();submit(sent);}}>
        {sent?<><label htmlFor="login-code">Six-digit code</label><input autoFocus id="login-code" className="code-input" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} required value={code} onChange={e=>setCode(e.target.value.replace(/\D/g,''))} placeholder="000000" disabled={busy}/></>:<><label htmlFor="login-email">NITK email address</label><input autoFocus id="login-email" type="email" autoComplete="email" required maxLength={254} pattern="[^@\s]+@nitk\.edu\.in" placeholder="yourname@nitk.edu.in" value={email} onChange={e=>setEmail(e.target.value)} disabled={busy}/><small>Only @nitk.edu.in email addresses are accepted.</small></>}
        {error&&<div className="error" role="alert">{error}</div>}
        <button className="primary" disabled={busy||!configured||(sent&&code.length!==6)} type="submit">{busy?<LoaderCircle size={18} className="spin"/>:null}{busy?'Please wait…':sent?'Verify and sign in':'Send me a code'}{!busy&&<ArrowRight size={17}/>}</button>
      </form>
      {sent&&<div className="auth-actions"><button disabled={busy||cooldown>0} onClick={()=>submit(false)}>{cooldown?`Resend in ${cooldown}s`:'Resend code'}</button><button disabled={busy} onClick={()=>{setSent(false);setCode('');setError('');}}>Use another email</button></div>}
      <div className="privacy-note"><ShieldCheck size={16}/><span>Secure email verification powered by WorkOS.</span></div>
    </section><p className="auth-footer">Independent student prototype · Not an official NITK service</p></main>;
}
