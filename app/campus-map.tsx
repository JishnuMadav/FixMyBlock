'use client';

import {useEffect,useRef,useState} from 'react';
import {Crosshair,MapPin,ExternalLink,X,Check,Search,LocateFixed} from 'lucide-react';
import campus from '../shared/campus.json';
import type {Map as LeafletMap,LayerGroup} from 'leaflet';

export type Pin={lat:number;lng:number;detail:string};
export type MapTicket={id:number;reference:string;title:string;status:string;sample:number;latitude:number|null;longitude:number|null};
export const googleLink=(lat:number,lng:number)=>`https://www.google.com/maps/search/?api=1&query=${lat},${lng}`;
export function inArea(lat:number,lng:number){const [[s,w],[n,e]]=campus.bounds;return lat>=s&&lat<=n&&lng>=w&&lng<=e;}
export function pinName(pin:Pin){
  let best=campus.landmarks[0],d=Infinity;
  for(const l of campus.landmarks){const x=(l.lat-pin.lat)**2+((l.lng-pin.lng)*Math.cos(pin.lat*Math.PI/180))**2;if(x<d){d=x;best=l;}}
  return Math.sqrt(d)*111195<200?`Near ${best.name}`:'Pinned campus location';
}

export function CampusMap({tickets=[],pin,onPick,onTicket,large=false}:{tickets?:MapTicket[];pin?:Pin|null;onPick?:(p:Pin)=>void;onTicket?:(id:number)=>void;large?:boolean}){
  const element=useRef<HTMLDivElement>(null);
  const map=useRef<LeafletMap|null>(null);
  const layer=useRef<LayerGroup|null>(null);
  const pickRef=useRef(onPick);pickRef.current=onPick;
  const ticketRef=useRef(onTicket);ticketRef.current=onTicket;
  const [ready,setReady]=useState(false),[failed,setFailed]=useState(false);
  useEffect(()=>{
    let disposed=false;let observer:ResizeObserver|undefined;
    import('leaflet').then(L=>{
      if(disposed||!element.current)return;
      const instance=L.map(element.current,{scrollWheelZoom:false,minZoom:14,maxZoom:19}).setView(campus.center as [number,number],large?16:15);
      map.current=instance;
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors'}).on('tileerror',()=>{if(!disposed)setFailed(true)}).addTo(instance);
      layer.current=L.layerGroup().addTo(instance);
      instance.on('click',(event)=>{if(pickRef.current)pickRef.current({lat:Number(event.latlng.lat.toFixed(7)),lng:Number(event.latlng.lng.toFixed(7)),detail:''})});
      observer=new ResizeObserver(()=>instance.invalidateSize());observer.observe(element.current);
      setReady(true);
    }).catch(()=>setFailed(true));
    return()=>{disposed=true;observer?.disconnect();map.current?.remove();map.current=null;layer.current=null;};
  },[large]);
  useEffect(()=>{
    if(!ready||!map.current||!layer.current)return;
    let cancelled=false;
    import('leaflet').then(L=>{
      if(cancelled||!map.current||!layer.current)return;
      const group=layer.current;group.clearLayers();
      for(const ticket of tickets){
        if(ticket.latitude==null||ticket.longitude==null)continue;
        const color=ticket.status==='Resolved'?'#80936a':ticket.status==='In progress'?'#be9344':'#476b4a';
        const marker=L.marker([ticket.latitude,ticket.longitude],{title:`${ticket.reference}: ${ticket.title}`,icon:L.divIcon({className:'incident-marker',html:`<span style="background:${color}">!</span>`,iconSize:[26,26],iconAnchor:[13,13]})}).addTo(group);
        const content=document.createElement('div');content.className='map-popup';
        const title=document.createElement('strong');title.textContent=ticket.title;content.append(title);
        const status=document.createElement('p');status.textContent=`${ticket.reference} · ${ticket.status}${ticket.sample?' · Fictional sample':''}`;content.append(status);
        if(ticketRef.current){const b=document.createElement('button');b.textContent='View report →';b.onclick=()=>ticketRef.current?.(ticket.id);content.append(b);}
        marker.bindPopup(content);
      }
      if(pin){
        const marker=L.marker([pin.lat,pin.lng],{draggable:!!pickRef.current,title:'Selected report location',icon:L.divIcon({className:'selected-pin',html:'<span>●</span>',iconSize:[34,34],iconAnchor:[17,30]})}).addTo(group);
        marker.on('dragend',()=>{const p=marker.getLatLng();pickRef.current?.({lat:Number(p.lat.toFixed(7)),lng:Number(p.lng.toFixed(7)),detail:pin.detail});});
        map.current.setView([pin.lat,pin.lng],Math.max(map.current.getZoom(),17),{animate:false});
      }
    });
    return()=>{cancelled=true};
  },[ready,tickets,pin]);
  return <div className={`real-campus-map ${large?'large':''}`}><div ref={element} className="leaflet-host" aria-label={onPick?'NITK location picker. Select a landmark below or click the map.':'NITK campus map with demo reports'}/>{!ready&&<div className="map-loading">Loading NITK campus…</div>}{failed&&<div className="map-error">Some map tiles could not load. You can still select a landmark below.</div>}{onPick&&<button type="button" className="map-center-pick" onClick={()=>{const c=map.current?.getCenter();if(c)onPick({lat:Number(c.lat.toFixed(7)),lng:Number(c.lng.toFixed(7)),detail:''})}}><Crosshair size={14}/>Use map centre</button>}</div>;
}

export function LocationPicker({open,pin,onClose,onSave}:{open:boolean;pin:Pin|null;onClose:()=>void;onSave:(p:Pin)=>void}){
  const dialog=useRef<HTMLDialogElement>(null);
  const [draft,setDraft]=useState<Pin|null>(pin),[query,setQuery]=useState(''),[error,setError]=useState(''),[locating,setLocating]=useState(false);
  useEffect(()=>{if(open){setDraft(pin);setError('');setQuery('');dialog.current?.showModal();}else dialog.current?.close();},[open,pin]);
  function pick(p:Pin){if(!inArea(p.lat,p.lng)){setError('That point is outside this campus demo area. Choose a point closer to NITK.');return;}setError('');setDraft({...p,detail:draft?.detail||p.detail});}
  function locate(){
    if(!navigator.geolocation){setError('Location is unavailable. Select a landmark instead.');return;}
    setLocating(true);setError('');
    navigator.geolocation.getCurrentPosition(p=>{setLocating(false);pick({lat:p.coords.latitude,lng:p.coords.longitude,detail:''})},()=>{setLocating(false);setError('Could not access your location. Select a landmark or place a pin instead.')},{enableHighAccuracy:true,timeout:10000,maximumAge:60000});
  }
  return <dialog ref={dialog} className="location-dialog" onCancel={onClose} onClick={e=>{if(e.target===dialog.current)onClose()}}><div className="location-dialog-content"><button className="dialog-close icon-button" aria-label="Close location picker" onClick={onClose}><X size={20}/></button><div className="eyebrow">NITK SURATHKAL · CAMPUS DEMO</div><h2>Show us where.</h2><p>Choose a landmark, or click the map to place a more precise pin.</p>{open&&<CampusMap large pin={draft} onPick={pick}/>}<div className="location-tools"><label className="search"><Search size={15}/><input aria-label="Find a campus landmark" placeholder="Find a campus landmark…" value={query} onChange={e=>setQuery(e.target.value)}/></label><button className="secondary" disabled={locating} onClick={locate}><LocateFixed size={14}/>{locating?'Locating…':'Use my location'}</button></div><div className="landmark-options">{campus.landmarks.filter(l=>l.name.toLowerCase().includes(query.toLowerCase())).map(l=><button key={l.id} onClick={()=>pick({lat:l.lat,lng:l.lng,detail:''})}><MapPin size={13}/>{l.name}</button>)}</div>{error&&<div role="alert" className="error">{error}</div>}{draft&&<div className="selected-location"><strong><MapPin size={15}/>{pinName(draft)}</strong><span>{draft.lat.toFixed(6)}, {draft.lng.toFixed(6)}<a href={googleLink(draft.lat,draft.lng)} target="_blank" rel="noreferrer">Open in Google Maps<ExternalLink size={12}/></a></span><label htmlFor="location-detail">A helpful detail (optional)</label><input id="location-detail" maxLength={200} placeholder="e.g. rear entrance, beside the first lamp" value={draft.detail} onChange={e=>setDraft({...draft,detail:e.target.value})}/></div>}<div className="location-save"><small>Approximate OpenStreetMap landmarks.<br/>Independent student demo, not an official NITK service.</small><button className="primary" disabled={!draft} onClick={()=>{if(draft)onSave(draft)}}><Check size={15}/>Use this location</button></div></div></dialog>;
}
