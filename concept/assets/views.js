/* Shared drawings for the concept: simulated camera pictures, seat map and icons.
   Plain SVG strings, so the same code works in Edge/WebView2 on Windows. */
(function(){
'use strict';
const {PEOPLE}=window.CutCut;
let uid=0;
function person(i,opts={}){
  const p=PEOPLE[i],id='g'+(uid++),talk=opts.talk?1:0;
  return `<svg viewBox="0 0 160 90" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
  <defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="var(--cam-bg1)"/><stop offset="1" stop-color="var(--cam-bg2)"/></linearGradient></defs>
  <rect width="160" height="90" fill="url(#${id})"/>
  <rect x="0" y="66" width="160" height="24" fill="var(--cam-table)" opacity=".7"/>
  <ellipse cx="80" cy="92" rx="38" ry="26" fill="var(--cam-skin)"/>
  <circle cx="80" cy="44" r="15" fill="var(--cam-skin)"/>
  <rect x="61" y="25" width="38" height="40" rx="3" fill="none" stroke="var(${p.color})" stroke-width="1.6" ${opts.faces===false?'opacity="0"':''}/>
  ${talk?`<rect x="74" y="51" width="12" height="3" rx="1.5" fill="var(${p.color})"/>`:''}
  </svg>`;
}
function bird(n){
  const seats=[[80,24],[124,50],[80,74],[36,50]].slice(0,4);
  return `<svg viewBox="0 0 160 90" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
  <rect width="160" height="90" fill="var(--cam-bg2)"/>
  <ellipse cx="80" cy="49" rx="40" ry="20" fill="var(--cam-table)"/>
  <rect x="66" y="31" width="28" height="7" rx="1.5" fill="var(--cam-skin)" opacity=".9"/>
  ${seats.map((s,i)=>`<circle cx="${s[0]}" cy="${s[1]}" r="7.5" fill="${i<n?`var(${PEOPLE[i].color})`:'var(--cam-skin)'}" opacity="${i<n?1:.35}"/>`).join('')}
  </svg>`;
}
function slide(no){
  return `<svg viewBox="0 0 160 90" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
  <rect width="160" height="90" fill="#F4F6F9"/><rect x="14" y="12" width="84" height="8" rx="2" fill="#1F3B66"/>
  <rect x="14" y="28" width="60" height="4" rx="2" fill="#8A97A8"/><rect x="14" y="37" width="70" height="4" rx="2" fill="#8A97A8"/><rect x="14" y="46" width="52" height="4" rx="2" fill="#8A97A8"/>
  <rect x="100" y="28" width="46" height="40" rx="3" fill="#C9D6EA"/><text x="146" y="83" font-size="7" text-anchor="end" fill="#59636F" font-family="Segoe UI,system-ui,sans-serif">Lysbilde ${no}</text></svg>`;
}
function audioOnly(){
  const bars=Array.from({length:28},(_,i)=>{const h=8+Math.abs(Math.sin(i*1.7))*26+((i*37)%11);return `<rect x="${24+i*4}" y="${45-h/2}" width="2.4" height="${h}" rx="1.2" fill="var(--eye)" opacity=".85"/>`}).join('');
  return `<svg viewBox="0 0 160 90" preserveAspectRatio="xMidYMid slice" aria-hidden="true"><rect width="160" height="90" fill="var(--cam-bg2)"/>${bars}
  <text x="80" y="82" font-size="8" text-anchor="middle" fill="var(--muted)" font-family="Segoe UI,system-ui,sans-serif">KUN LYD</text></svg>`;
}
function shot(key,s,opts={}){
  if(!key||key==='BIRD')return bird(s.session.n);
  if(key==='CONTENT')return slide(s.slide);
  if(key==='AUDIO')return audioOnly();
  const i=+key[1]-1;return person(i,{talk:s.mics[i]&&s.mics[i].state==='snakker',faces:opts.faces});
}
/* Top-down seating map: presenter at the mixer, guests clockwise. */
function seatMap(n,opts={}){
  const pos=[[300,330],[470,200],[300,82],[130,200]];
  const lvl=opts.levels||[];
  return `<svg viewBox="0 0 600 420" role="img" aria-label="Bordplan med ${n} plasser">
  <ellipse cx="300" cy="205" rx="170" ry="96" fill="var(--surface-2)" stroke="var(--line)" stroke-width="2"/>
  <rect x="246" y="250" width="108" height="34" rx="6" fill="var(--surface)" stroke="var(--line)" stroke-width="2"/>
  <text x="300" y="272" text-anchor="middle" font-size="15" fill="var(--muted)" font-family="var(--f-ui)" letter-spacing="1">RØDECASTER</text>
  ${pos.map((p,i)=>{const on=i<n,c=`var(${PEOPLE[i].color})`,r=34+(on&&lvl[i]?Math.min(16,lvl[i]*16):0);
    return `<g opacity="${on?1:.32}">
      ${on&&lvl[i]?`<circle cx="${p[0]}" cy="${p[1]}" r="${r}" fill="${c}" opacity=".22"/>`:''}
      <circle cx="${p[0]}" cy="${p[1]}" r="34" fill="${on?c:'var(--surface)'}" stroke="${on?c:'var(--line)'}" stroke-width="3" ${on?'':'stroke-dasharray="6 6"'}/>
      <text x="${p[0]}" y="${p[1]+11}" text-anchor="middle" font-size="32" font-weight="700" fill="${on?'#fff':'var(--faint)'}" font-family="var(--f-display)">${i+1}</text>
      <text x="${p[0]}" y="${p[1]+(i===2?-48:62)}" text-anchor="middle" font-size="19" font-weight="600" fill="var(--ink)" font-family="var(--f-ui)">${i===0?'Programleder':PEOPLE[i].name}</text>
    </g>`}).join('')}
  </svg>`;
}
const ICON={
  sun:'<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4.5" fill="none" stroke="currentColor" stroke-width="2"/><g stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8"/></g></svg>',
  moon:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>',
  cam:'<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="2.5" y="6" width="13" height="12" rx="2.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M15.5 10.5l6-3.5v10l-6-3.5z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>',
  mic:'<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="8.5" y="2.5" width="7" height="12" rx="3.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M5 11.5a7 7 0 0 0 14 0M12 18.5V22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
  card:'<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="2.5" y="5" width="19" height="14" rx="2.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M2.5 9.5h19" stroke="currentColor" stroke-width="2"/></svg>',
  check:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  help:'<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .9-1 1.6v.6M12 17.2v.1" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
  grid:'<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="7.5" height="7.5" rx="1.5" fill="none" stroke="currentColor" stroke-width="2"/><rect x="13.5" y="3" width="7.5" height="7.5" rx="1.5" fill="none" stroke="currentColor" stroke-width="2"/><rect x="3" y="13.5" width="7.5" height="7.5" rx="1.5" fill="none" stroke="currentColor" stroke-width="2"/><rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.5" fill="none" stroke="currentColor" stroke-width="2"/></svg>',
  sliders:'<svg viewBox="0 0 24 24" aria-hidden="true"><g stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0"/></g><g fill="none" stroke="currentColor" stroke-width="2"><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/></g></svg>',
  rec:'<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="4.5" fill="currentColor"/></svg>',
  pulse:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.5 12h4l2.5-6 4.5 12 2.5-6h5.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  wand:'<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 20L15 9M13 7l4 4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M18 2.5v3M16.5 4h3M20.5 9v2M19.5 10h2M9 3v2M8 4h2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>',
  list:'<svg viewBox="0 0 24 24" aria-hidden="true"><g stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01"/></g></svg>',
  gear:'<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3.2" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 2.5v2.6M12 18.9v2.6M21.5 12h-2.6M5.1 12H2.5M18.7 5.3l-1.8 1.8M7.1 16.9l-1.8 1.8M18.7 18.7l-1.8-1.8M7.1 7.1L5.3 5.3" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'
};
const LOGO=`<svg class="logo" viewBox="20 50 190 90" role="img" aria-label="CutCut Studio">
  <g fill="var(--eye)"><rect x="32" y="90" width="7" height="20" rx="3.5"/><rect x="44" y="78" width="7" height="44" rx="3.5"/><rect x="56" y="68" width="7" height="64" rx="3.5"/><rect x="68" y="82" width="7" height="36" rx="3.5"/><rect x="80" y="92" width="7" height="16" rx="3.5"/></g>
  <g stroke="var(--pgm)" stroke-width="6" stroke-linecap="round"><line x1="100" y1="128" x2="114" y2="72"/><line x1="116" y1="128" x2="130" y2="72"/></g>
  <rect x="158" y="56" width="44" height="30" rx="5" fill="none" stroke="var(--bleed)" stroke-width="1.5"/>
  <rect x="151" y="72" width="44" height="30" rx="5" fill="none" stroke="var(--bleed)" stroke-width="1.5"/>
  <rect x="144" y="88" width="48" height="34" rx="5" fill="var(--eye-soft)" stroke="var(--eye)" stroke-width="2.5"/>
  <circle cx="182" cy="97" r="4" fill="var(--pgm)"/></svg>`;
/* Theme: three states. Stored per screen; touch defaults to dark. */
function initTheme(key,def){
  const stored=window.CutCut.theme.get(key);const v=stored||def;
  if(v==='light'||v==='dark')document.documentElement.setAttribute('data-theme',v);else document.documentElement.removeAttribute('data-theme');
  return v||'system';
}
function isDark(){const a=document.documentElement.getAttribute('data-theme');if(a)return a==='dark';return matchMedia('(prefers-color-scheme: dark)').matches}
function toggleTheme(key){const v=isDark()?'light':'dark';document.documentElement.setAttribute('data-theme',v);window.CutCut.theme.set(key,v);return v}
window.CutCutViews={person,bird,slide,audioOnly,shot,seatMap,ICON,LOGO,initTheme,isDark,toggleTheme};
})();
