import "./muscle-session-map.css";

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
    const secondary=item.secondary_muscles||ex.secondary_muscles||[];
    if(Array.isArray(secondary))secondary.forEach(m=>add(m,sets,.28));
  });
  // Foco da sessão é fallback e nunca deve dominar músculos confirmados pelos exercícios.
  (focus||[]).forEach(m=>{const k=normalizeMuscle(m);if(k&&!load[k])load[k]=.75});
  return load;
}

function Region({id,load,children}){const value=load[id]||0;if(!value)return children;const max=Math.max(...Object.values(load),1);const strength=Math.max(.45,Math.min(1,value/max));return <g className="muscle-region active"style={{"--muscle-strength":strength}}>{children}</g>}

function BodyBase(){return <g className="body-base">
  <circle cx="55" cy="22" r="13"/><path d="M44 36 Q37 43 33 59 L26 98 32 102 40 72 42 113 36 157 41 219 50 219 53 165 55 119 57 165 60 219 69 219 74 157 68 113 70 72 78 102 84 98 77 59 Q73 43 66 36 Q55 42 44 36Z"/>
</g>}

function Front({load}){return <svg viewBox="0 0 110 235" aria-label="Vista frontal"><BodyBase/>
  <Region id="upper_chest" load={load}><path d="M43 49 Q55 43 67 49 L65 58 Q55 54 45 58Z"/></Region>
  <Region id="mid_chest" load={load}><path d="M43 58 Q55 54 67 58 L65 72 Q55 77 45 72Z"/></Region>
  <Region id="front_delts" load={load}><ellipse cx="39" cy="51" rx="7" ry="9"/><ellipse cx="71" cy="51" rx="7" ry="9"/></Region>
  <Region id="side_delts" load={load}><path d="M33 50 Q28 58 30 68 L36 65 39 54Z"/><path d="M77 50 Q82 58 80 68 L74 65 71 54Z"/></Region>
  <Region id="biceps" load={load}><path d="M31 67 Q27 77 28 90 L34 91 38 68Z"/><path d="M79 67 Q83 77 82 90 L76 91 72 68Z"/></Region>
  <Region id="brachialis" load={load}><path d="M29 84 L27 99 33 101 35 87Z"/><path d="M81 84 L83 99 77 101 75 87Z"/></Region>
  <Region id="abs" load={load}><rect x="48" y="74" width="14" height="40" rx="5"/><path d="M55 75V113M48 88H62M48 101H62" className="muscle-cut"/></Region>
  <Region id="obliques" load={load}><path d="M43 74 Q39 86 42 109 L48 112 48 76Z"/><path d="M67 74 Q71 86 68 109 L62 112 62 76Z"/></Region>
  <Region id="quads" load={load}><path d="M41 116 Q37 137 40 158 L51 158 53 118Z"/><path d="M69 116 Q73 137 70 158 L59 158 57 118Z"/></Region>
  <Region id="adductors" load={load}><path d="M51 119 L55 121 53 158 48 154Z"/><path d="M59 119 L55 121 57 158 62 154Z"/></Region>
  <Region id="calves" load={load}><path d="M40 164 Q37 188 42 209 L50 209 51 166Z"/><path d="M70 164 Q73 188 68 209 L60 209 59 166Z"/></Region>
</svg>}

function Back({load}){return <svg viewBox="0 0 110 235" aria-label="Vista posterior"><BodyBase/>
  <Region id="traps" load={load}><path d="M48 36 L55 42 62 36 66 54 55 61 44 54Z"/></Region>
  <Region id="upper_back" load={load}><path d="M42 50 Q55 59 68 50 L66 72 Q55 79 44 72Z"/></Region>
  <Region id="rear_delts" load={load}><ellipse cx="38" cy="52" rx="8" ry="9"/><ellipse cx="72" cy="52" rx="8" ry="9"/></Region>
  <Region id="lats" load={load}><path d="M43 65 Q37 77 42 101 L50 110 52 75Z"/><path d="M67 65 Q73 77 68 101 L60 110 58 75Z"/></Region>
  <Region id="triceps" load={load}><path d="M31 66 Q27 80 29 94 L35 95 38 68Z"/><path d="M79 66 Q83 80 81 94 L75 95 72 68Z"/></Region>
  <Region id="glutes" load={load}><path d="M42 109 Q43 126 54 128 L54 111Z"/><path d="M68 109 Q67 126 56 128 L56 111Z"/></Region>
  <Region id="hamstrings" load={load}><path d="M41 128 Q38 145 41 160 L52 160 54 130Z"/><path d="M69 128 Q72 145 69 160 L58 160 56 130Z"/></Region>
  <Region id="calves" load={load}><path d="M40 164 Q37 188 42 209 L50 209 51 166Z"/><path d="M70 164 Q73 188 68 209 L60 209 59 166Z"/></Region>
</svg>}

export default function MuscleSessionMap({items=[],exercises=[],focus=[]}){
  const load=buildSessionMuscles(items,exercises,focus);
  const ranked=Object.entries(load).sort((a,b)=>b[1]-a[1]).slice(0,4);
  return <div className="session-muscle-map" data-testid="session-muscle-map">
    <div className="session-muscle-map__views"><div><Front load={load}/><span>FRENTE</span></div><div><Back load={load}/><span>COSTAS</span></div></div>
    <div className="session-muscle-map__legend" aria-label="Músculos trabalhados hoje">
      {ranked.length?ranked.map(([id,value],i)=><span key={id} className={i===0?"primary":""}><i/>{LABELS[id]||id}{value>=1&&<small>{Math.round(value)}s</small>}</span>):<span><i/>Sessão geral</span>}
    </div>
  </div>
}
