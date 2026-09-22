export const resumeDate = () => { const d=new Date(); return [d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-'); };

export const resumeStorageKey = userId => `forge_workout_resume_v1:${userId}`;
export function workoutResumeContext(userId, program, session, items, date=resumeDate()) {
  if (!userId || !session || program.rest_day || !items.length) return null;
  return JSON.stringify([userId,date,program.id||program.template_id||'',program.week||'',session.day,session.label,
    items.map(item=>[item.exercise_id,item.sets,item.reps])]);
}
export function readWorkoutResume(userId, context, recentSets=[]) {
  if (!userId || !context) return null;
  try {
    const saved=JSON.parse(localStorage.getItem(resumeStorageKey(userId))||'null');
    if(saved?.context!==context || saved.started!==true || !Number.isFinite(saved.startedAt))return null;
    const [,date,,,day,,items]=JSON.parse(context),done={...saved.done},inputs={...saved.inputs};
    for(const row of [...recentSets].sort((a,b)=>new Date(a.created_at)-new Date(b.created_at))){
      const at=new Date(row.created_at),n=Number(row.set_number),item=items.find(i=>i[0]===row.exercise_id);
      const rowDate=[at.getFullYear(),String(at.getMonth()+1).padStart(2,'0'),String(at.getDate()).padStart(2,'0')].join('-');
      if(rowDate!==date||Number(row.session_day)!==Number(day)||!item||!Number.isInteger(n)||n<1||n>Number(item[1]))continue;
      done[row.exercise_id+(n-1)]=true;
      inputs[`${row.exercise_id}-${n-1}`]={weight:row.weight,reps:row.reps,rir:row.rir};
    }
    return {...saved,done,inputs};
  } catch { return null; }
}
export function saveWorkoutResume(userId, context, state) {
  if (!userId || !context || !state.started) return;
  try { localStorage.setItem(resumeStorageKey(userId),JSON.stringify({...state,context,updatedAt:Date.now()})); } catch { /* The server draft remains available if storage is blocked. */ }
}
export function clearWorkoutResume(userId) {
  try { localStorage.removeItem(resumeStorageKey(userId)); } catch { /* Storage may be unavailable. */ }
}
