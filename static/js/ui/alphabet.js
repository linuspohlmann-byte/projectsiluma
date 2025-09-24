// alphabet.js — Pre-Level Alphabet mini-app
// Public API: initAlphabet(), startAlphabet()

const $ = (sel)=> document.querySelector(sel);
const $$ = (sel)=> Array.from(document.querySelectorAll(sel));

let AB = {
  letters: [], target: 'en', native: 'de',
  needed: 2, attempts: 0, correct: 0,
  roundTimer: null, timePerRoundMs: 10000, current: null
};

// Local fallback alphabet generator for supported languages
function fallbackAlphabet(lang){
  const map = {
    en: 'A B C D E F G H I J K L M N O P Q R S T U V W X Y Z'.split(' '),
    de: 'A Ä B C D E F G H I J K L M N O Ö P Q R S ß T U Ü V W X Y Z'.split(' '),
    fr: 'A B C D E F G H I J K L M N O P Q R S T U V W X Y Z'.split(' '),
    es: 'A B C D E F G H I J K L M N Ñ O P Q R S T U V W X Y Z'.split(' '),
    it: 'A B C D E F G H I J K L M N O P Q R S T U V W X Y Z'.split(' '),
    pt: 'A B C D E F G H I J K L M N O P Q R S T U V W X Y Z'.split(' '),
    ru: 'А Б В Г Д Е Ё Ж З И Й К Л М Н О П Р С Т У Ф Х Ц Ч Ш Щ Ъ Ы Ь Э Ю Я'.split(' '),
    tr: 'A B C Ç D E F G Ğ H I İ J K L M N O Ö P R S Ş T U Ü V Y Z'.split(' '),
    ka: 'ა ბ გ დ ე ვ ზ თ ი კ ლ მ ნ ო პ ჟ რ ს ტ უ ფ ქ ღ ყ შ ჩ ც ძ წ ჭ ხ ჯ ჰ'.split(' ')
  };
  const arr = map[lang] || map['en'];
  return arr.map(ch=>({ char: ch, ipa: '', audio_url: '', ok: 0 }));
}

function ensureAlphabetUI(){
  if(document.getElementById('alphabet-card')) return;
  const st = document.createElement('style'); st.id = 'alph-style'; st.textContent = `
    #alphabet-card .opt{display:flex;gap:10px;justify-content:center;margin-top:12px}
    #alphabet-card .opt button{min-width:120px; font-size:32px; padding:20px 24px}
    #alphabet-card .ipa{font-size:18px;opacity:.9;margin-top:10px}
    #alphabet-card .center{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;padding:14px 0 10px}
    #alphabet-card .hud{display:flex;align-items:center;justify-content:center;gap:10px;margin-bottom:8px}
    #alphabet-card .timer{height:6px;background:#1b2130;border-radius:999px;overflow:hidden;width:240px}
    #alphabet-card .timer>i{display:block;height:100%;width:100%;background:linear-gradient(90deg,var(--accent),#7cc4ff);transition:width .1s linear}
  `; document.head.appendChild(st);

  const card = document.createElement('section');
  card.id = 'alphabet-card'; card.className = 'card'; card.style.display = 'none';
  card.innerHTML = `
    <div class="row" style="justify-content:space-between; align-items:center">
      <h3 style="margin:0" data-i18n="alphabet.title">Alphabet</h3>
      <button id="ab-exit" class="secondary" data-i18n="alphabet.back_button">Zurück</button>
    </div>
    <div class="hud"><div class="pill" id="ab-progress">0 / 0</div></div>
    <div class="center">
      <div id="ab-ipa" class="ipa"></div>
      <div class="timer"><i id="ab-time"></i></div>
      <audio id="ab-audio" preload="auto" style="display:none"></audio>
      <div class="opt">
        <button id="ab-o0" class="btn secondary"></button>
        <button id="ab-o1" class="btn secondary"></button>
        <button id="ab-o2" class="btn secondary"></button>
      </div>
      <div class="row" style="justify-content:center;margin-top:10px">
        <button id="ab-replay" class="btn" title="Audio erneut" data-i18n-title="alphabet.audio_replay" data-i18n="alphabet.audio_replay_button">🔊 Nochmal</button>
      </div>
    </div>`;
  const anchor = document.getElementById('levels-card') || document.body;
  anchor.parentNode ? anchor.parentNode.insertBefore(card, anchor) : document.body.appendChild(card);
}

function showOnlyAlphabet(){
  ['#levels-card','#words-card','#lesson','#evaluation-card','#practice-card'].forEach(id=>{ const el=$(id); if(el) el.style.display='none'; });
  const ab = $('#alphabet-card'); if(ab) ab.style.display='';
}

async function fetchAlphabet(){
  const lang = AB.target;
  // Try primary endpoint
  try{
    const r = await fetch(`/api/alphabet?language=${encodeURIComponent(lang)}`);
    const js = await r.json();
    if(Array.isArray(js) && js.length){
      const out = js.map(x=>({ char:String(x.char||x.letter||'').trim(), ipa:String(x.ipa||'').trim(), audio_url:String(x.audio_url||'').trim(), ok:0 }))
                    .filter(x=>x.char);
      if(out.length) return out;
    }
  }catch(_){}
  // Try ensure endpoint
  try{
    const r = await fetch('/api/alphabet/ensure',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({language:lang})});
    const js = await r.json();
    if(js && Array.isArray(js.letters)){
      const out = js.letters.map(x=>({ char:String(x.char||x.letter||'').trim(), ipa:String(x.ipa||'').trim(), audio_url:String(x.audio_url||'').trim(), ok:0 }))
                             .filter(x=>x.char);
      if(out.length) return out;
    }
  }catch(_){}
  // Fallback local alphabet for the language
  return fallbackAlphabet(lang);
}

async function ensureAudioFor(ch){
  const a = document.getElementById('ab-audio'); if(!a) return null;
  const lang = AB.target;
  try{
    // Use the new alphabet-specific TTS endpoint for phonetic pronunciation
    const r = await fetch('/api/alphabet/tts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({letter:ch,language:lang})});
    const js = await r.json();
    if(js && js.success && js.audio_url) return js.audio_url;
  }catch(_){}
  return null;
}

function updateProgress(){
  const need = AB.needed * AB.letters.length;
  const have = AB.letters.reduce((s,x)=> s + Math.min(AB.needed, x.ok||0), 0);
  const el = document.getElementById('ab-progress'); if(el) el.textContent = `${have} / ${need}`;
}

function pickRound(){
  const pool = AB.letters.filter(x=> (x.ok||0) < AB.needed);
  const tgt = pool[Math.floor(Math.random()*pool.length)];
  const others = AB.letters.filter(x=> x!==tgt);
  const shuffled = others.sort(()=>Math.random()-0.5).slice(0,2);
  const options = [tgt, ...shuffled].sort(()=>Math.random()-0.5);
  const answerIdx = options.indexOf(tgt);
  AB.current = { answer: answerIdx, options };
}

async function renderRound(){
  if(!AB.current) pickRound();
  const { options, answer } = AB.current;
  const tgt = options[answer];
  $('#ab-ipa').textContent = tgt.ipa || '';
  
  // Reset and enable all buttons
  const buttons = ['ab-o0', 'ab-o1', 'ab-o2'];
  options.forEach((o,i)=>{ 
    const b = document.getElementById('ab-o'+i); 
    if(b) {
      b.textContent = o.char;
      b.disabled = false;
      b.style.backgroundColor = '';
      b.style.color = '';
      b.style.borderColor = '';
    }
  });
  
  const a = document.getElementById('ab-audio'); if(a){
    let url = tgt.audio_url; if(!url){ url = await ensureAudioFor(tgt.char); tgt.audio_url = url||''; }
    if(url){ a.src = url; try{ await a.play(); }catch(_){ } }
  }
  const bar = document.getElementById('ab-time'); if(bar){ bar.style.width='100%'; }
  if(AB.roundTimer){ clearInterval(AB.roundTimer); AB.roundTimer=null; }
  const start = Date.now();
  AB.roundTimer = setInterval(()=>{
    const dt = Date.now()-start; const left = Math.max(0, AB.timePerRoundMs - dt);
    const pct = Math.round(left/AB.timePerRoundMs*100);
    if(bar) bar.style.width = pct+'%';
    if(left<=0){ clearInterval(AB.roundTimer); AB.roundTimer=null; handleAnswer(-1); }
  }, 100);
}

function handleAnswer(idx){
  AB.attempts++;
  const { answer, options } = AB.current || {answer:-1, options:[]};
  const correct = (idx===answer);
  
  // Disable all buttons to prevent multiple clicks
  const buttons = ['ab-o0', 'ab-o1', 'ab-o2'];
  buttons.forEach(btnId => {
    const btn = document.getElementById(btnId);
    if (btn) {
      btn.disabled = true;
    }
  });
  
  // Play sound effect based on correctness
  if (window.soundManager) {
    if (correct) {
      window.soundManager.playCorrect();
    } else {
      window.soundManager.playIncorrect();
    }
  }
  
  // Visual feedback for buttons
  buttons.forEach((btnId, i) => {
    const btn = document.getElementById(btnId);
    if (btn) {
      if (i === answer) {
        // Correct answer - green highlight
        btn.style.backgroundColor = '#10b981';
        btn.style.color = 'white';
        btn.style.borderColor = '#10b981';
      } else if (i === idx && !correct) {
        // Wrong answer selected - red highlight
        btn.style.backgroundColor = '#ef4444';
        btn.style.color = 'white';
        btn.style.borderColor = '#ef4444';
      } else {
        // Reset other buttons
        btn.style.backgroundColor = '';
        btn.style.color = '';
        btn.style.borderColor = '';
      }
    }
  });
  
  if(correct){ AB.correct++; const tgt = options[answer]; tgt.ok = (tgt.ok||0)+1; }
  updateProgress();
  const done = AB.letters.every(x=> (x.ok||0) >= AB.needed);
  if(done){ return finishAlphabet(); }
  
  // Reset button styles and re-enable buttons after a short delay
  setTimeout(() => {
    buttons.forEach(btnId => {
      const btn = document.getElementById(btnId);
      if (btn) {
        btn.style.backgroundColor = '';
        btn.style.color = '';
        btn.style.borderColor = '';
        btn.disabled = false;
      }
    });
    AB.current = null; 
    pickRound(); 
    renderRound();
  }, 1500);
}

function finishAlphabet(){
  if(AB.roundTimer){ clearInterval(AB.roundTimer); AB.roundTimer=null; }
  const evalEl = document.getElementById('evaluation-card');
  if(evalEl){
    ['#levels-card','#words-card','#lesson','#practice-card','#alphabet-card'].forEach(id=>{ const el=$(id); if(el) el.style.display='none'; });
    evalEl.style.display='';
    const t = evalEl.querySelector('.eval-title'); if(t) t.textContent=window.t ? window.t('alphabet.completed', 'Alphabet abgeschlossen 🎉') : 'Alphabet abgeschlossen 🎉';
    const pct = AB.attempts>0 ? Math.round((AB.correct/AB.attempts)*100) : 0;
    const ring = document.getElementById('eval-ring');
    const label = document.getElementById('eval-ring-txt');
    const C = 2*Math.PI*42, off = C*(1 - Math.max(0,Math.min(100,pct))/100);
    if(ring){ ring.setAttribute('stroke-dasharray', String(C.toFixed(2))); ring.setAttribute('stroke-dashoffset', String(off)); }
    if(label){ label.textContent = pct + '%'; }
    [0,1,2,3,4,5].forEach(s=>{ const el = document.querySelector(`#evaluation-card .num[data-status="${s}"]`); if(el) el.textContent='–'; });
  }
}

function bindHandlers(){
  ['ab-o0','ab-o1','ab-o2'].forEach((id,i)=>{ const b=document.getElementById(id); if(b) b.onclick=()=>{ if(AB.roundTimer){ clearInterval(AB.roundTimer); AB.roundTimer=null; } handleAnswer(i); }; });
  const replay = document.getElementById('ab-replay'); if(replay) replay.onclick = async ()=>{
    const { options, answer } = AB.current||{}; const tgt = options && options[answer]; if(!tgt) return;
    const a = document.getElementById('ab-audio'); if(a && tgt.audio_url){ try{ a.pause(); a.currentTime=0; await a.play(); }catch(_){ } }
  };
  const exit = document.getElementById('ab-exit');
    if(exit) exit.onclick = ()=>{
    if(AB.roundTimer){ clearInterval(AB.roundTimer); AB.roundTimer=null; }
    const a = document.getElementById('ab-audio');
    if(a){ try{ a.pause(); a.removeAttribute('src'); }catch(_){ } }
    AB.current=null; AB.letters=[]; AB.attempts=0; AB.correct=0;
    const ab = document.getElementById('alphabet-card'); if(ab) ab.style.display='none';
    const lv = document.getElementById('levels-card'); if(lv) lv.style.display='';
    };

  // Add event listeners for library tab and show-words (same as exit)
  const libraryTab = document.querySelector('[data-tab="library"]');
  if(libraryTab){
    libraryTab.addEventListener('click', ()=>{
      if(AB.roundTimer){ clearInterval(AB.roundTimer); AB.roundTimer=null; }
      const a = document.getElementById('ab-audio');
      if(a){ try{ a.pause(); a.removeAttribute('src'); }catch(_){ } }
      AB.current=null; AB.letters=[]; AB.attempts=0; AB.correct=0;
      const ab = document.getElementById('alphabet-card'); if(ab) ab.style.display='none';
    });
  }
  const navWords = document.getElementById('show-words');
  if(navWords){
    navWords.addEventListener('click', ()=>{
      if(AB.roundTimer){ clearInterval(AB.roundTimer); AB.roundTimer=null; }
      const a = document.getElementById('ab-audio');
      if(a){ try{ a.pause(); a.removeAttribute('src'); }catch(_){ } }
      AB.current=null; AB.letters=[]; AB.attempts=0; AB.correct=0;
      const ab = document.getElementById('alphabet-card'); if(ab) ab.style.display='none';
    });
  }
}

export async function startAlphabet(){
  AB.target = $('#target-lang')?.value || 'en';
  AB.native = localStorage.getItem('siluma_native') || 'de';
  ensureAlphabetUI();
  showOnlyAlphabet();
  AB.target = document.getElementById('target-lang')?.value || 'en';
  AB.native = localStorage.getItem('siluma_native') || 'de';
  AB.letters = await fetchAlphabet();
  if(!AB.letters.length){
    const card = document.getElementById('alphabet-card');
    if(card){
      card.style.display='';
      card.innerHTML = `<div class="row" style="justify-content:space-between; align-items:center"><h3 style="margin:0" data-i18n="alphabet.title">Alphabet</h3><button id="ab-exit" class="secondary" data-i18n="alphabet.back_button">Zurück</button></div><div class="pill" style="margin-top:10px" data-i18n="alphabet.load_error">Alphabet konnte nicht geladen werden</div>`;
      const exit = document.getElementById('ab-exit'); if(exit) exit.onclick = ()=>{ card.style.display='none'; const lv=document.getElementById('levels-card'); if(lv) lv.style.display=''; };
    }
    return;
  }
  AB.letters.forEach(x=> x.ok=0);
  AB.attempts = 0; AB.correct = 0; AB.current=null;
  updateProgress();
  bindHandlers();
  pickRound();
  renderRound();
}

function ensureAlphabetEntry(){
  // Container mit "Alphabet - Anfangen" entfernt - wird nicht mehr benötigt
  // Das Alphabet wird nur noch über den "Alphabet" Button in den Stats-Actions gestartet
}

export function initAlphabet(){
  ensureAlphabetUI();
  // Ensure alphabet entry is visible and functional
  ensureAlphabetEntry();
}

// Legacy
if(typeof window!== 'undefined'){ window.startAlphabet = startAlphabet; }