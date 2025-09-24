export const state = {
  _lt_level: 1,
  _eval_context: 'level'
};
export const setLevel = (n)=>{ state._lt_level = Number(n)||1; };
export const getLevel = ()=> state._lt_level;
export const setEvalContext = (s)=>{ state._eval_context = s; };
export const getEvalContext = ()=> state._eval_context;