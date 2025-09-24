const j = async (u, opt)=>{ const r = await fetch(u, opt); return r.json(); };
export const api = {
  words: ()=> j('/api/words'),
  wordsCountMax: (language)=> j(`/api/words/count_max${language?`?language=${encodeURIComponent(language)}`:''}`),
  wordGet: (word,language)=> j(`/api/word?word=${encodeURIComponent(word)}&language=${encodeURIComponent(language||'')}`),
  wordUpsert: (payload)=> {
    const headers = { 'Content-Type': 'application/json' };
    const nativeLanguage = localStorage.getItem('siluma_native') || 'en';
    headers['X-Native-Language'] = nativeLanguage;
    return j('/api/word/upsert',{method:'POST',headers,body:JSON.stringify(payload)});
  },
  wordEnrich: (payload)=> j('/api/word/enrich',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}),
  wordTTS: (payload)=> j('/api/word/tts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}),
  levelsSummary: ()=> j('/api/levels/summary'),
};