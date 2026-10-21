/* CutCut Studio – concept simulator.
   A small, simplified version of the rule engine with simulated speech, so the screens
   can be shown without equipment. In the real app the state comes from the engine on
   the studio PC over WebSocket; here it lives in the browser.
   Touch and tech share one simulation across tabs/iframes via BroadcastChannel:
   one tab leads (runs the engine), the others mirror it and send commands. */
(function(){
'use strict';
const PEOPLE=[
  {id:'P1',name:'Programleder',short:'Programl.',color:'--p1',colorName:'magenta',role:'host'},
  {id:'P2',name:'Gjest 1',short:'Gjest 1',color:'--p2',colorName:'cyan',role:'guest'},
  {id:'P3',name:'Gjest 2',short:'Gjest 2',color:'--p3',colorName:'lilla',role:'guest'},
  {id:'P4',name:'Gjest 3',short:'Gjest 3',color:'--p4',colorName:'oransje',role:'guest'}];
const PRESETS={
  rolig:{vad:.7,dom:9,confirm:1200,minShot:4,cross:1.5,silence:4,monolog:25},
  standard:{vad:.6,dom:6,confirm:800,minShot:2.5,cross:1.0,silence:3,monolog:15},
  energisk:{vad:.5,dom:4,confirm:500,minShot:1.8,cross:.8,silence:2,monolog:10}};
const FEATURES=[
  {k:'bird',name:'Fugleperspektiv',ids:'B1–B5',d:'Åpning, krysstale, latter og stillhet',on:true,base:true},
  {k:'content',name:'Laptop som content',ids:'CT1–CT6',d:'Ny slide vises; video holdes',on:true,base:true},
  {k:'video_confirm',name:'Videolag bekrefter',ids:'V1 V2 V5',d:'Munnbevegelse bekrefter tale',on:false},
  {k:'reactions',name:'Reaksjonsklipp',ids:'R1–R3',d:'Lytter som nikker eller ler',on:false},
  {k:'framing_variety',name:'Vekslende utsnitt',ids:'F1–F3',d:'Nær og halvnær off air',on:false},
  {k:'slow_zoom',name:'Langsom zoom',ids:'Z1–Z3',d:'Maks 10 % over 15 s',on:false},
  {k:'layouts',name:'Layouter (PiP/quad)',ids:'L1–L4',d:'ATEM-makroer via Companion',on:false},
  {k:'live_transcript',name:'Live tekst',ids:'NB-Whisper',d:'Tekst per mic, ca. 3 s forsinket',on:true},
  {k:'turn_prediction',name:'Forvarsel om turbytte',ids:'VAP',d:'Armer preview tidligere',on:false},
  {k:'ai_tracking',name:'AI-tracking (OBSBOT)',ids:'AT1–AT6',d:'Kameraet følger personen',on:false}];
const LINES={host:['Velkommen til en ny episode.','Hva tenker du om det?','Det er et godt poeng.','La oss gå litt videre.','Kan du utdype det?','Hvordan begynte det hele?'],
  guest:['Det kommer litt an på hvordan man ser det.','Jeg tror det handler om tillit.','Det så vi allerede i fjor.','Der er jeg faktisk uenig.','For oss var det helt avgjørende.','Vi testet det på studentene først.']};
const HEALTH=[
  {id:'H-NET',name:'Nett og porter, alle enheter',grp:'Nett',val:'11/11 svarer, 4 ms'},
  {id:'H-ATEM-1',name:'ATEM-tilkobling og tilstand',grp:'ATEM',val:'Program og preview leses'},
  {id:'H-ATEM-2',name:'Format, inngangsnavn, multiview',grp:'ATEM',val:'1080p50 · lik fasit'},
  {id:'H-ATEM-3',name:'Makroer og mediaspillere',grp:'ATEM',val:'14 makroer · MP1 Kun lyd'},
  {id:'H-ATEM-4',name:'ISO-disk og opptak',grp:'ATEM',val:'402 GB ledig · ca. 9 t'},
  {id:'H-COMP-1',name:'Companion API og knappesider',grp:'Companion',val:'38 ms · cutcut_pages v3'},
  {id:'H-CAM-1',name:'CAM 1 Canon CR-N300',grp:'Kamera',val:'XC · manuell · 5600 K'},
  {id:'H-CAM-2',name:'CAM 2 OBSBOT Tail 2',grp:'Kamera',val:'VISCA + OSC · 5600 K'},
  {id:'H-CAM-3',name:'CAM 3 OBSBOT Tail 2',grp:'Kamera',val:'VISCA + OSC · 5600 K'},
  {id:'H-CAM-4',name:'CAM 4 OBSBOT Tail 2',grp:'Kamera',val:'VISCA + OSC · 5600 K'},
  {id:'H-CAM-MOVE',name:'Ingen ukjent kamerabevegelse',grp:'Kamera',val:'Alle i ro'},
  {id:'H-AUD-1',name:'ASIO-strøm fra RØDECaster',grp:'Lyd',val:'20 kanaler · 48 kHz · 0 dropouts'},
  {id:'H-AUD-2',name:'Støy og kanalkart per mic',grp:'Lyd',val:'Under fasit + 6 dB'},
  {id:'H-AUD-3',name:'Mic aktiv, men mangler i hovedmiks (S6)',grp:'Lyd',val:'Ingen dempet mic i bruk'},
  {id:'H-VID-1',name:'Capture-bilde og rutekart',grp:'Video',val:'INOGENI · 1080p50'},
  {id:'H-VID-2',name:'Forsinkelse ATEM → PC',grp:'Video',val:'112 ms (fasit 110)'},
  {id:'H-PRL-1',name:'Pearl status og lagring',grp:'Opptak',val:'812 GB · 41 °C'},
  {id:'H-PRL-2',name:'Opptak kjører når det skal',grp:'Opptak',val:'OK'},
  {id:'H-CARD-1',name:'Kortleser TWN3 (COM4)',grp:'Innlogging',val:'Port åpen'},
  {id:'H-NTNU-1',name:'NTNU-API',grp:'Innlogging',val:'Testoppslag 420 ms'},
  {id:'H-PROC',name:'Prosesser: core, audio, vision, stt',grp:'PC',val:'Hjerteslag OK'},
  {id:'H-PC',name:'Disk, GPU, klokke',grp:'PC',val:'GPU 54 °C · NTP 3 ms'}];
const WIZARD=[
  {n:1,name:'Nett og IP',what:'Fast IP på alt utstyr etter IP-planen',fix:false,state:'ok'},
  {n:2,name:'PC og Windows',what:'Strømplan, USB-strømsparing, oppdateringstider, drivere',fix:true,state:'ok'},
  {n:3,name:'ATEM',what:'1080p50, inngangsnavn, multiview på HDMI ut 2, mediaspillere',fix:true,state:'ok'},
  {n:4,name:'Kameraer',what:'IP-styring, 1080p50, manuell hvitbalanse, grenser og presets',fix:true,state:'warn'},
  {n:5,name:'RØDECaster',what:'Faderkart, multitrack pre-fader, firmware 1.7.6',fix:false,state:'ok'},
  {n:6,name:'Multiview',what:'INOGENI som kilde, rutekart, forsinkelse',fix:true,state:'ok'},
  {n:7,name:'Companion',what:'Side 10 og 11 importert, ATEM og Pearl tilkoblet',fix:false,state:'ok'},
  {n:8,name:'Makroer og grafikk',what:'PiP/quad-makroer, Kun lyd-grafikk',fix:true,state:'todo'},
  {n:9,name:'Pearl og kort',what:'Opptaker, NTP, TWN3 i COM-modus, NTNU-API',fix:false,state:'ok'},
  {n:10,name:'Generalprøve',what:'5 min i skyggemodus med alle deltakere',fix:false,state:'todo'}];
const FAULTS={
  'no-audio':{label:'Lyd fra RØDECaster borte',health:'H-AUD-1',sev:'err',touch:'Noe er galt med lyden. Teknikeren er varslet.'},
  'pearl-full':{label:'Pearl: under 60 min lagring',health:'H-PRL-1',sev:'warn'},
  'cam3-off':{label:'CAM 3 svarer ikke',health:'H-CAM-3',sev:'err'},
  'mute-p2':{label:'Gjest 1 dempet på mikseren (S6)',health:'H-AUD-3',sev:'warn'}};
const USERS=[{name:'Kari Nordmann',first:'Kari',user:'karino'},{name:'Ola Hansen',first:'Ola',user:'olaha'},{name:'Ingrid Berg',first:'Ingrid',user:'ingridb'}];

const rnd=(a,b)=>a+Math.random()*(b-a);
const pick=a=>a[Math.floor(Math.random()*a.length)];
const fmt1=x=>x.toFixed(1).replace('.',',');
const clock=ms=>{const s=Math.max(0,Math.floor(ms/1000));const h=Math.floor(s/3600),m=Math.floor(s/60)%60,ss=s%60;return (h?h+':':'')+String(m).padStart(2,'0')+':'+String(ss).padStart(2,'0')};

function freshState(){
  const f={};FEATURES.forEach(x=>f[x.k]=x.on);
  return {v:0,t:0,helpAt:0,auto:true,lock:false,preset:'standard',features:f,laptop:true,faults:{},
    session:{phase:'idle',user:null,n:2,mode:'video',recStart:0,recEnd:0,countdownEnd:0,doneAt:0},
    mics:PEOPLE.map(()=>({lvl:-60,vad:0,run:0,gap:999,state:'stille'})),
    pgm:'BIRD',pvw:null,pvState:'',age:0,next:'Studio klart. Venter på innlogging.',
    content:'STATIC',slide:3,log:[],tx:[],sample:null,
    rec:{pearl:false,iso:false,pearlFreeGb:812,isoFreeGb:402},sessions:[
      {user:'Ingrid Berg',start:'09:05',dur:'41:12',mode:'Video',n:3,status:'Lastet opp'},
      {user:'Ola Hansen',start:'11:30',dur:'27:48',mode:'Kun lyd',n:2,status:'Lastet opp'}]};
}

class Sim{
  constructor(){
    this.s=freshState();this.hist=[];this.listeners=new Set();
    this.id=Math.random().toString(36).slice(2);this.leader=false;this.lastHeard=0;
    this.events=[];this.planUntil=0;this.lastMain=0;this.waitT=0;this.overlapT=0;this.silT=0;
    this.insert=null;this.prevShot=null;this.lastCutT=-1e9;this.nextSlideAt=20000;this.slideFlash=0;this.txSeen=new Set();this.txQ=[];
    try{this.ch=new BroadcastChannel('cutcut-concept');this.ch.onmessage=e=>this.onMsg(e.data)}catch(e){this.ch=null}
    this.started=performance.now();
    if(!this.ch)this.leader=true;else this.post({type:'hello',from:this.id});
    this.last=performance.now();
    this.sent={};setInterval(()=>this.loop(),100);
  }
  on(fn){this.listeners.add(fn);fn(this.s,this.hist)}
  emit(){this.listeners.forEach(fn=>fn(this.s,this.hist))}
  post(m){if(this.ch)try{this.ch.postMessage(m)}catch(e){}}
  onMsg(m){
    if(!m||m.from===this.id)return;
    if(m.type==='state'){
      if(this.leader&&m.from<this.id)this.leader=false;
      if(!this.leader){this.lastHeard=performance.now();const old=this.s,ns=m.state;
        ['log','tx','sessions'].forEach(k=>{if(!(k in ns))ns[k]=old[k]});
        if(m.samples)m.samples.forEach(x=>{this.hist.push(x);if(this.hist.length>600)this.hist.shift()});
        this.s=ns;if(!document.hidden)this.emit()}
    } else if(m.type==='cmd'&&this.leader){this.apply(m.cmd,m.arg)}
    else if(m.type==='hello'&&this.leader){this.forceFull=true}
  }
  cmd(c,a){if(this.leader)this.apply(c,a);else this.post({type:'cmd',from:this.id,cmd:c,arg:a})}
  loop(){
    const now=performance.now();
    if(!this.leader&&now-this.started>700&&now-this.lastHeard>1200)this.leader=true;
    if(!this.leader){this.last=now;return}
    let dt=Math.min(1000,now-this.last);this.last=now;
    while(dt>0){const d=Math.min(30,dt);this.step(d);dt-=d}
    this.s.v++;
    if(this.ch){const st={...this.s},keys={log:this.s.log[0],tx:this.s.tx[0],sessions:this.s.sessions[0]};
      for(const k in keys){if(this.sent[k]===keys[k]&&this.sent[k+'n']===this.s[k].length)delete st[k];else{this.sent[k]=keys[k];this.sent[k+'n']=this.s[k].length}}
      if(this.forceFull){this.forceFull=false;st.log=this.s.log;st.tx=this.s.tx;st.sessions=this.s.sessions}
      this.post({type:'state',from:this.id,state:st,samples:this.newSamples});}
    this.newSamples=[];if(!document.hidden)this.emit();
  }
  get P(){return [...Array(this.s.session.n).keys()]}
  log(to,rule,why){this.s.log.unshift({t:this.s.t,to,rule,why});if(this.s.log.length>60)this.s.log.pop()}
  shotLabel(k){if(!k)return '';if(k==='BIRD')return 'CAM 5 · Fugleperspektiv';if(k==='CONTENT')return 'IN 6 · Laptop';if(k==='AUDIO')return 'MP 1 · Kun lyd-grafikk';const i=+k[1]-1;return `CAM ${i+1} · ${PEOPLE[i].name}`}
  apply(c,a){
    const s=this.s,se=s.session;
    switch(c){
      case 'scan':{const u=a||pick(USERS);se.phase='ready';se.user=u;this.log(null,'—',`Innlogget med kort: ${u.user} (kortnummer lagres ikke, I8)`);break}
      case 'n':se.n=Math.max(1,Math.min(4,a));break;
      case 'mode':se.mode=a;break;
      case 'start':if(s.faults['no-audio']){this.log(null,'S4','Start avvist: ingen lyd fra RØDECaster');break}
        se.phase='countdown';se.countdownEnd=s.t+3200;this.log(null,'—',`${se.user?se.user.first:'Bruker'} trykket Start (${se.n} ${se.n===1?'person':'personer'}, ${se.mode==='audio'?'kun lyd':'video'})`);break;
      case 'stop':if(se.phase==='rec'){se.phase='done';se.recEnd=s.t;se.doneAt=s.t;s.rec.pearl=false;s.rec.iso=false;
        s.sessions.unshift({user:se.user?se.user.name:'Tekniker',start:new Date().toTimeString().slice(0,5),dur:clock(se.recEnd-se.recStart),mode:se.mode==='audio'?'Kun lyd':'Video',n:se.n,status:'Venter på opplasting'});
        this.log(null,'—',`Opptak stoppet av ${a||'bruker'} etter ${clock(se.recEnd-se.recStart)} (I7)`);this.cut('BIRD','—','Opptak ferdig, tilbake til total')}break;
      case 'logout':se.phase='idle';se.user=null;this.log(null,'—','Logget ut');break;
      case 'auto':s.auto=!!a;this.log(null,'—',a?'AUTO slått på':'AUTO slått av, ATEM beholder bildet');break;
      case 'lock':s.lock=!!a;this.log(null,'—',a?'Bildet låst av tekniker':'Lås sluppet');break;
      case 'cut':this.cut(a,'M','Manuelt kutt fra tekniker');this.manualUntil=s.t+5000;break;
      case 'preset':s.preset=a;this.log(null,'—',`Forhåndsvalg «${a}»`);break;
      case 'feature':s.features[a.k]=a.on;this.log(null,'—',`${FEATURES.find(f=>f.k===a.k).name} ${a.on?'slått på':'slått av'}`);break;
      case 'fault':if(a.on)s.faults[a.k]=1;else delete s.faults[a.k];this.log(null,FAULTS[a.k].sev==='err'?'S':'—',`${a.on?'Feil simulert':'Feil fjernet'}: ${FAULTS[a.k].label}`);break;
      case 'laptop':s.laptop=!!a;break;
      case 'slide':this.slideFlash=600;s.slide++;break;
      case 'help':s.helpAt=s.t;this.log(null,'—',`${se.user?se.user.first:'Bruker'} ba om hjelp fra touch-skjermen`);break;
      case 'help-ok':s.helpAt=0;break;
      case 'tech-rec':if(se.phase!=='rec'){se.phase='rec';se.recStart=s.t;se.user=se.user||{name:'Tekniker',first:'Tekniker',user:'tekniker'};s.rec.pearl=true;s.rec.iso=true;this.log(null,'—','Opptak startet fra teknikervinduet')}break;
    }
    this.s.v++;this.emit();
  }
  cut(to,rule,why){
    const s=this.s;if(to===s.pgm&&rule!=='M')return;
    this.prevShot=s.pgm;s.pgm=to;s.age=0;this.waitT=0;this.lastCutT=s.t;s.pvw=null;
    this.log(to,rule,why);
  }
  plan(){
    const s=this.s,P=this.P,n=P.length;const pickOther=x=>{const o=P.filter(i=>i!==x);return o.length?pick(o):x};
    let who=n===1?0:(Math.random()<.45?0:pickOther(this.lastMain));if(who===this.lastMain&&n>1)who=pickOther(this.lastMain);
    const st=Math.max(this.planUntil,s.t)+rnd(n===1?700:250,n===1?1800:900);
    const dur=n===1?rnd(12000,26000):rnd(4000,11000);const e=st+dur;
    let p=st;while(p<e){const ph=Math.min(e,p+rnd(1200,3400));this.events.push({who,s:p,e:ph,k:'tale'});p=ph+rnd(170,420)}
    let end=e;
    if(n>1){for(let k=0;k<Math.floor(dur/4000);k++)if(Math.random()<.5){const b=rnd(st+800,e-800);this.events.push({who:pickOther(who),s:b,e:b+rnd(300,800),k:'mm'})}
      if(Math.random()<.13){const o=pickOther(who);this.events.push({who:o,s:e-rnd(1200,2000),e:e+rnd(1500,3200),k:'tale'});this.lastMain=o;end=this.events[this.events.length-1].e}else this.lastMain=who}
    this.planUntil=end;
  }
  step(dt){
    const s=this.s,se=s.session,R=PRESETS[s.preset];s.t+=dt;const t=s.t;
    // session phases
    if(se.phase==='countdown'&&t>=se.countdownEnd){se.phase='rec';se.recStart=t;s.rec.pearl=true;s.rec.iso=se.mode==='video';this.log(null,'—','Opptak startet: Pearl Nexus'+(se.mode==='video'?' og ATEM ISO':'')+(se.user?` · ${se.user.user}`:''));
      if(se.mode==='audio')this.cut('AUDIO','A','Kun lyd: grafikk fra mediespiller 1');else this.cut('BIRD','B1','Åpner på fugleperspektiv')}
    if(se.phase==='done'&&t-se.doneAt>30000){se.phase='idle';se.user=null;this.log(null,'—','Logget ut automatisk etter 30 s')}
    const talking=se.phase==='ready'||se.phase==='countdown'||se.phase==='rec';
    if(talking&&t>this.planUntil-1500)this.plan();
    if(!talking){this.events=[];this.planUntil=t}
    this.events=this.events.filter(e=>e.e>t-1000);
    // content
    if(s.laptop&&s.features.content){if(t>this.nextSlideAt&&se.phase==='rec'){this.slideFlash=600;s.slide++;this.nextSlideAt=t+rnd(30000,50000)}
      if(this.slideFlash>0){this.slideFlash-=dt;s.content='NEW_SLIDE'}else s.content='STATIC'}else s.content='NO_SIGNAL';
    // mic signals
    const P=this.P,noAudio=!!s.faults['no-audio'];
    const sp=PEOPLE.map((_,i)=>{if(i>=se.n||!talking)return null;let k=null;for(const e of this.events)if(e.who===i&&t>=e.s&&t<e.e)k=e.k;return k});
    s.mics.forEach((m,i)=>{
      if(i>=se.n){m.lvl=-60;m.vad=0;m.run=0;m.gap=999;m.state='ubrukt';return}
      const k=sp[i],others=sp.some((o,j)=>j!==i&&o);let lvl,v;
      if(noAudio){lvl=-90;v=0}
      else if(k){lvl=(k==='mm'?-23:-17)+rnd(-3,3);v=rnd(.8,.97)}
      else if(others){lvl=-32+rnd(-3,3);v=rnd(.3,.6)}else{lvl=-58+rnd(-2,2);v=rnd(0,.08)}
      m.lvl=m.lvl*.5+lvl*.5;m.vad=m.vad*.6+v*.4});
    const maxOther=i=>Math.max(-90,...P.filter(j=>j!==i).map(j=>s.mics[j].lvl));
    const muted=i=>i===1&&s.faults['mute-p2'];
    P.forEach(i=>{const m=s.mics[i];const audio=m.vad>R.vad&&(se.n===1||m.lvl-maxOther(i)>=R.dom);
      if(audio){m.run+=dt;m.gap=0}else{m.gap+=dt;if(m.gap>250)m.run=0}
      m.state=noAudio?'ingen lyd':muted(i)&&m.run>0?'dempet':m.run>=R.confirm?'snakker':m.run>0?'bekrefter':(m.vad>R.vad?'lekkasje':'stille')});
    const isAct=i=>s.mics[i].run>0&&s.mics[i].gap<=250&&!muted(i);
    const actives=P.filter(isAct);const nOver=actives.filter(i=>s.mics[i].run>=300).length;
    this.overlapT=nOver>=2?this.overlapT+dt:0;this.silT=actives.length?0:this.silT+dt;
    s.age+=dt;
    // sample for timeline (10 Hz)
    if(Math.floor(t/100)!==Math.floor((t-dt)/100)){s.sample={m:PEOPLE.map((_,i)=>i>=se.n?0:isAct(i)&&s.mics[i].run>=R.confirm?2:(s.mics[i].vad>R.vad?1:0)),p:s.pgm};this.hist.push(s.sample);if(this.hist.length>600)this.hist.shift();(this.newSamples||(this.newSamples=[])).push(s.sample)}
    // transcript
    if(s.features.live_transcript&&talking){for(const e of this.events){if(e.k!=='tale'||t<e.s||this.txSeen.has(e))continue;this.txSeen.add(e);if(Math.random()<.65)this.txQ.push({at:e.s+3200,who:e.who,text:pick(LINES[e.who===0?'host':'guest'])})}
      while(this.txQ.length&&this.txQ[0].at<=t){const x=this.txQ.shift();if(x.who<se.n){s.tx.unshift({t:x.at-3200,who:x.who,text:x.text});if(s.tx.length>8)s.tx.pop()}}}
    if(this.txSeen.size>400)this.txSeen.clear();
    // decisions
    s.pvw=null;s.pvState='';
    if(se.phase!=='rec'){s.next=se.phase==='idle'?'Studio klart. Venter på innlogging.':se.phase==='ready'?`${se.user?se.user.first:'Bruker'} er logget inn og velger oppsett.`:se.phase==='countdown'?'Starter opptak …':'Opptak ferdig.';return}
    if(se.mode==='audio'){s.next='Kun lyd: ingen kutt. Grafikken står på program.';return}
    if(noAudio){if(s.pgm!=='BIRD')this.cut('BIRD','S4','Ingen lyd fra RØDECaster over 2 s');s.next='Ingen lyd: står på total og prøver å åpne ASIO på nytt (S4).';return}
    const cp=s.pgm[0]==='P'?+s.pgm[1]-1:null;
    if(this.manualUntil&&t<this.manualUntil){s.next=`Manuelt kutt: motoren venter ${fmt1((this.manualUntil-t)/1000)} s`;return}
    if(t-se.recStart<4000){s.next=`Åpning på fugleperspektiv i ${fmt1((4000-(t-se.recStart))/1000)} s til (B1)`;return}
    let want=null,rule='',why='',direct=false;
    if(this.insert){if(s.age>=this.insert.dur){const b=this.insert.back;this.insert=null;if(b!=null&&isAct(b)){want='P'+(b+1);rule='H4';why=`Tilbake til ${PEOPLE[b].name}`}}
      else{s.next=`Innslag (${this.insert.label}), tilbake om ${fmt1((this.insert.dur-s.age)/1000)} s`}}
    if(!want&&!this.insert){
      if(s.content==='NEW_SLIDE'&&s.pgm!=='CONTENT'&&nOver<2){want='CONTENT';rule='CT2';why=`Ny slide (${s.slide}) på laptop`;this.pendingInsert={label:'ny slide',dur:6000,back:cp};direct=true}
      else if(this.overlapT>=R.cross*1000&&se.n>1&&s.features.bird&&s.pgm!=='BIRD'){want='BIRD';rule=se.n>=3?'B2':'T5';why=`${nOver} snakker samtidig i ${fmt1(this.overlapT/1000)} s`}
      else{const best=actives.filter(i=>s.mics[i].run>=R.confirm).sort((a,b)=>(s.mics[b].run*(b===0?1.1:1))-(s.mics[a].run*(a===0?1.1:1)))[0];
        if(best!=null&&best!==cp){want='P'+(best+1);rule=cp!=null&&isAct(cp)?'T4':'T2';why=`${PEOPLE[best].name} aktiv ${fmt1(s.mics[best].run/1000)} s (krav ${fmt1(R.confirm/1000)} s), ${Math.round(s.mics[best].lvl-maxOther(best))} dB over andre`}
        else if(best!=null&&best===cp&&se.n>1&&s.age>=R.monolog*1000&&s.mics[cp].gap>=170){const lis=cp===0?pick(P.filter(i=>i!==0)):0;want='P'+(lis+1);rule='T7';why=`${PEOPLE[cp].name} har snakket ${fmt1(s.age/1000)} s, reaksjon fra ${PEOPLE[lis].name}`;this.pendingInsert={label:'reaksjon',dur:2500,back:cp};direct=true}
        else if(!actives.length&&this.silT>=R.silence*1000&&s.pgm!=='BIRD'&&s.features.bird){want='BIRD';rule='T8';why=`Ingen aktiv mic på ${fmt1(this.silT/1000)} s`}}
    }
    if(want&&want!==s.pgm){
      s.pvw=want;s.pvState='READY';
      if(!s.auto){s.next=`AUTO er av. Motoren ville kuttet til ${this.shotLabel(want)} (${rule})`}
      else if(s.lock){s.next=`LÅST. Motoren ville kuttet til ${this.shotLabel(want)} (${rule})`}
      else if(want==='P3'&&s.faults['cam3-off']){s.pvState='ARMED';s.next='CAM 3 svarer ikke: velger total i stedet (S1)';if(s.pgm!=='BIRD')this.cut('BIRD','S1','CAM 3 utilgjengelig')}
      else if(!direct&&s.age<R.minShot*1000){s.pvState='ARMED';s.next=`${this.shotLabel(want)} på preview, venter på minste bildelengde: ${fmt1((R.minShot*1000-s.age)/1000)} s (T3)`}
      else if(!direct&&want[0]==='P'&&cp!=null&&isAct(cp)&&s.mics[cp].gap<200&&this.waitT<1500){this.waitT+=dt;s.next=`${this.shotLabel(want)} klar på preview, venter på pause hos ${PEOPLE[cp].name} (K2)`}
      else{const k=this.waitT>=1500?' · tatt ved maks ventetid (K3)':this.waitT>0?` · tatt i pause etter ${Math.round(this.waitT)} ms (K2)`:(want[0]==='P'?' · turbytte (K1)':'');
        this.cut(want,rule,why+k);if(this.pendingInsert){this.insert=this.pendingInsert;this.pendingInsert=null}}
    } else if(!this.insert){this.pendingInsert=null;
      s.next=t-this.lastCutT<5000?`Holder bildet · sterkere krav til nytt kutt i ${fmt1((5000-(t-this.lastCutT))/1000)} s (H1)`:cp!=null&&isAct(cp)?`Holder ${this.shotLabel(s.pgm)}. Reaksjonsbilde om ${fmt1(Math.max(0,R.monolog-s.age/1000))} s (T7)`:actives.length?'Holder bildet':`Stille i ${fmt1(this.silT/1000)} s`}
  }
}
window.CutCut={Sim,PEOPLE,PRESETS,FEATURES,HEALTH,WIZARD,FAULTS,USERS,clock,fmt1,
  theme:{get(def){try{return localStorage.getItem('cutcut-theme-'+def)||null}catch(e){return null}},
    set(key,v){try{localStorage.setItem('cutcut-theme-'+key,v)}catch(e){}}}};
})();
