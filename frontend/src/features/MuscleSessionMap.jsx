import "./muscle-session-map.css";
import "./workout-premium.css";

const ALIASES={
  "peitoral superior":"upper_chest","upper chest":"upper_chest",upper_chest:"upper_chest",
  "peitoral esternal":"mid_chest","peitoral":"mid_chest",chest:"mid_chest",mid_chest:"mid_chest",
  "deltoide anterior":"front_delts","deltóide anterior":"front_delts",front_delts:"front_delts",
  "deltoide lateral":"side_delts","deltóide lateral":"side_delts",side_delts:"side_delts",
  "deltoide posterior":"rear_delts","deltóide posterior":"rear_delts",rear_delts:"rear_delts",
  "dorsais / largura":"lats",dorsais:"lats",latissimus:"lats",lats:"lats",
  "costas / espessura":"upper_back","costas":"upper_back","upper back":"upper_back",upper_back:"upper_back",
  trapezio:"traps","trapézio":"traps",traps:"traps",
  biceps:"biceps","bíceps":"biceps",braquial:"brachialis",brachialis:"brachialis",
  triceps:"triceps","tríceps":"triceps",
  quadriceps:"quads","quadríceps":"quads",quads:"quads",
  posteriores:"hamstrings",posterior:"hamstrings",hamstrings:"hamstrings",
  gluteos:"glutes","glúteos":"glutes",glutes:"glutes",
  adutores:"adductors",adductors:"adductors",
  panturrilhas:"calves",panturrilha:"calves",calves:"calves",
  abdomen:"abs","abdômen":"abs",abs:"abs",
  obliquos:"obliques","oblíquos":"obliques",obliques:"obliques"
};

const LABELS={
  upper_chest:"Peitoral superior",mid_chest:"Peitoral",front_delts:"Delt. anterior",side_delts:"Delt. lateral",
  rear_delts:"Delt. posterior",lats:"Dorsais",upper_back:"Costas",traps:"Trapézio",biceps:"Bíceps",
  brachialis:"Braquial",triceps:"Tríceps",quads:"Quadríceps",hamstrings:"Posteriores",glutes:"Glúteos",
  adductors:"Adutores",calves:"Panturrilhas",abs:"Abdômen",obliques:"Oblíquos"
};

const UPPER=new Set(["upper_chest","mid_chest","front_delts","side_delts","rear_delts","lats","upper_back","traps","biceps","brachialis","triceps"]);
const LOWER=new Set(["quads","hamstrings","glutes","adductors","calves"]);
const CORE=new Set(["abs","obliques"]);
const ZONE_LABEL={upper:"SUPERIOR",lower:"INFERIOR",full:"FULL BODY"};

function strip(value){return String(value||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").trim().toLowerCase()}
export function normalizeMuscle(value){const raw=String(value||"").trim();return ALIASES[raw.toLowerCase()]||ALIASES[strip(raw)]||null}

export function buildSessionMuscles(items=[],exerciseCatalog=[],focus=[]){
  const byId=new Map((exerciseCatalog||[]).map(x=>[x.id,x]));
  const load={};
  const add=(name,sets=1,weight=1)=>{const key=normalizeMuscle(name);if(key)load[key]=(load[key]||0)+Math.max(1,Number(sets)||1)*weight};
  (items||[]).forEach(item=>{
    const ex=byId.get(item.exercise_id)||{};
    const sets=Number(item.sets)||1;
    add(item.primary_muscle||ex.primary_muscle||ex.muscle||ex.target,sets,1);
    const secondary=item.secondary_muscles||ex.secondary_muscles||ex.secondary||[];
    if(Array.isArray(secondary))secondary.forEach(m=>add(m,sets,.28));
  });
  (focus||[]).forEach(m=>{const k=normalizeMuscle(m);if(k&&!load[k])load[k]=.75});
  return load;
}

export function getSessionZone(load={}){
  let upper=0,lower=0,core=0;
  Object.entries(load||{}).forEach(([id,value])=>{
    const amount=Number(value)||0;
    if(UPPER.has(id))upper+=amount;
    else if(LOWER.has(id))lower+=amount;
    else if(CORE.has(id))core+=amount;
  });
  if(!upper&&!lower&&core)return "upper";
  if(!lower&&upper)return "upper";
  if(!upper&&lower)return "lower";
  if(!upper&&!lower)return "full";
  const ratio=upper/Math.max(lower,.01);
  if(ratio>=1.45)return "upper";
  if(ratio<=.69)return "lower";
  return "full";
}

function AnatomyDefs({prefix}){return <defs>
  <linearGradient id={`${prefix}-body`} x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#373a3d"/><stop offset=".48" stopColor="#1a1c1f"/><stop offset="1" stopColor="#090a0b"/></linearGradient>
  <linearGradient id={`${prefix}-inactive`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#33363a"/><stop offset="1" stopColor="#151719"/></linearGradient>
  <linearGradient id={`${prefix}-active`} x1="0" y1="0" x2=".72" y2="1"><stop offset="0" stopColor="#ff9d78"/><stop offset=".46" stopColor="#e96343"/><stop offset="1" stopColor="#9f3327"/></linearGradient>
  <filter id={`${prefix}-glow`} x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2.3" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
</defs>}

function activeFor(id,zone){if(zone==="full")return true;if(zone==="upper")return UPPER.has(id)||CORE.has(id);return LOWER.has(id)}
function Region({id,zone,prefix,children}){const active=activeFor(id,zone);return <g className={`muscle-region${active?" active":""}`} data-muscle={id} fill={`url(#${prefix}-${active?"active":"inactive"})`} filter={active?`url(#${prefix}-glow)`:undefined}>{children}</g>}
function Silhouette({prefix}){return <g className="anatomy-silhouette" fill={`url(#${prefix}-body)`}><ellipse cx="90" cy="36" rx="18" ry="23"/><path d="M78 56 Q90 64 102 56 L108 72 Q126 76 139 91 L145 122 137 160 128 160 125 126 121 106 116 140 111 190 105 213 75 213 69 190 64 140 59 106 55 126 52 160 43 160 35 122 41 91 Q54 76 72 72Z"/><path d="M76 207 Q63 225 62 263 L59 324 66 399 82 399 87 326 90 261 93 326 98 399 114 399 121 324 118 263 Q117 225 104 207Z"/></g>}

function Front({zone}){const p="front";return <svg viewBox="0 0 180 420" aria-label={`Vista frontal · ${ZONE_LABEL[zone]}`} role="img"><AnatomyDefs prefix={p}/><Silhouette prefix={p}/><g className="anatomy-lines"><path d="M78 58 Q90 69 102 58M90 70V206M64 91Q90 109 116 91M68 126Q90 139 112 126M75 151H105M76 170H104M77 188H103M66 218Q76 234 88 244M114 218Q104 234 92 244M87 257L78 322M93 257L102 322"/></g>
  <Region id="upper_chest" zone={zone} prefix={p}><path d="M68 88 Q77 77 89 80 L89 104 Q76 104 66 99Z"/><path d="M112 88 Q103 77 91 80 L91 104 Q104 104 114 99Z"/></Region>
  <Region id="mid_chest" zone={zone} prefix={p}><path d="M66 100 Q77 103 89 105 L89 130 Q76 132 66 119Z"/><path d="M114 100 Q103 103 91 105 L91 130 Q104 132 114 119Z"/></Region>
  <Region id="front_delts" zone={zone} prefix={p}><path d="M63 82 Q49 82 43 95 Q45 108 57 111 L67 98Z"/><path d="M117 82 Q131 82 137 95 Q135 108 123 111 L113 98Z"/></Region>
  <Region id="side_delts" zone={zone} prefix={p}><path d="M47 91 Q38 103 39 121 L48 119 57 105Z"/><path d="M133 91 Q142 103 141 121 L132 119 123 105Z"/></Region>
  <Region id="biceps" zone={zone} prefix={p}><path d="M44 116 Q36 133 40 151 L51 152 57 119Z"/><path d="M136 116 Q144 133 140 151 L129 152 123 119Z"/></Region>
  <Region id="brachialis" zone={zone} prefix={p}><path d="M40 145 Q36 157 39 169 L49 166 51 151Z"/><path d="M140 145 Q144 157 141 169 L131 166 129 151Z"/></Region>
  <Region id="abs" zone={zone} prefix={p}><path d="M79 128 Q90 123 101 128 L103 191 Q90 202 77 191Z"/><path className="muscle-cut" d="M90 130V194M79 148H101M78 166H102M78 183H102"/></Region>
  <Region id="obliques" zone={zone} prefix={p}><path d="M68 126 Q62 145 68 188 L78 194 79 130Z"/><path d="M112 126 Q118 145 112 188 L102 194 101 130Z"/></Region>
  <Region id="quads" zone={zone} prefix={p}><path d="M72 215 Q62 240 64 284 L69 321 83 321 88 258 87 221Z"/><path d="M108 215 Q118 240 116 284 L111 321 97 321 92 258 93 221Z"/></Region>
  <Region id="adductors" zone={zone} prefix={p}><path d="M86 220 Q78 247 81 294 L88 309 90 257Z"/><path d="M94 220 Q102 247 99 294 L92 309 90 257Z"/></Region>
  <Region id="calves" zone={zone} prefix={p}><path d="M66 325 Q59 352 66 386 L78 389 82 331Z"/><path d="M114 325 Q121 352 114 386 L102 389 98 331Z"/></Region>
</svg>}

function Back({zone}){const p="back";return <svg viewBox="0 0 180 420" aria-label={`Vista posterior · ${ZONE_LABEL[zone]}`} role="img"><AnatomyDefs prefix={p}/><Silhouette prefix={p}/><g className="anatomy-lines"><path d="M90 59V209M70 88Q90 77 110 88M62 110Q90 129 118 110M72 146Q90 156 108 146M75 184Q90 193 105 184M65 218Q78 227 89 234M115 218Q102 227 91 234M87 257L77 321M93 257L103 321"/></g>
  <Region id="traps" zone={zone} prefix={p}><path d="M79 61 L90 75 101 61 111 91 90 112 69 91Z"/></Region>
  <Region id="upper_back" zone={zone} prefix={p}><path d="M63 90 Q77 82 89 106 L89 136 Q72 129 61 111Z"/><path d="M117 90 Q103 82 91 106 L91 136 Q108 129 119 111Z"/></Region>
  <Region id="rear_delts" zone={zone} prefix={p}><path d="M62 82 Q48 83 42 96 Q45 110 58 111 L68 97Z"/><path d="M118 82 Q132 83 138 96 Q135 110 122 111 L112 97Z"/></Region>
  <Region id="lats" zone={zone} prefix={p}><path d="M62 109 Q55 127 61 165 Q67 188 81 199 L87 136 76 121Z"/><path d="M118 109 Q125 127 119 165 Q113 188 99 199 L93 136 104 121Z"/></Region>
  <Region id="triceps" zone={zone} prefix={p}><path d="M44 113 Q36 133 41 156 L52 153 57 117Z"/><path d="M136 113 Q144 133 139 156 L128 153 123 117Z"/></Region>
  <Region id="glutes" zone={zone} prefix={p}><path d="M72 205 Q63 223 67 246 Q76 256 88 251 L89 211Z"/><path d="M108 205 Q117 223 113 246 Q104 256 92 251 L91 211Z"/></Region>
  <Region id="hamstrings" zone={zone} prefix={p}><path d="M67 247 Q61 270 66 319 L82 321 88 255Z"/><path d="M113 247 Q119 270 114 319 L98 321 92 255Z"/></Region>
  <Region id="calves" zone={zone} prefix={p}><path d="M66 324 Q58 350 66 386 L78 389 82 331Z"/><path d="M114 324 Q122 350 114 386 L102 389 98 331Z"/></Region>
</svg>}

export default function MuscleSessionMap({items=[],exercises=[],focus=[]}){
  const load=buildSessionMuscles(items,exercises,focus);
  const zone=getSessionZone(load);
  const ranked=Object.entries(load).sort((a,b)=>b[1]-a[1]).slice(0,4);
  return <div className="session-muscle-map" data-testid="session-muscle-map" data-zone={zone}>
    <div className="session-muscle-map__zone"><i/>{ZONE_LABEL[zone]}</div>
    <div className="session-muscle-map__views"><div className="anatomy-view"><Front zone={zone}/><span>FRENTE</span></div><div className="anatomy-view"><Back zone={zone}/><span>COSTAS</span></div></div>
    <div className="session-muscle-map__legend" aria-label="Músculos trabalhados hoje">{ranked.length?ranked.map(([id,value],i)=><span key={id} className={i===0?"primary":""}><i/>{LABELS[id]||id}{value>=1&&<small>{Math.round(value)}s</small>}</span>):<span><i/>Sessão geral</span>}</div>
  </div>
}
