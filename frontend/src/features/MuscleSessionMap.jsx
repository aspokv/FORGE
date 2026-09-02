import {memo} from "react";
import "./anatomy-assets.css";
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
const ASSET_KEYS=new Set(["push","pull","upper","lower","full-body","chest","back-width","back-thickness","shoulders","arms","glutes","hamstrings","quads","calves","core","legs-quads","legs-posterior"]);

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

export function getAnatomyAssetKey(load={},sessionLabel=""){
  const label=strip(sessionLabel);
  const named=[
    [/full\s*body/,"full-body"],[/push|peito.*triceps/,"push"],[/pull|costas.*biceps/,"pull"],
    [/upper|superior/,"upper"],[/lower|inferior/,"lower"],[/pernas|legs/,"lower"],
    [/peito|chest/,"chest"],[/costas|back/,"back-width"],[/ombros|shoulders/,"shoulders"],[/bracos|arms/,"arms"],
  ];
  const namedMatch=named.find(([pattern])=>pattern.test(label));
  if(namedMatch)return namedMatch[1];
  const value=id=>Number(load[id])||0;
  const scores={
    chest:value("upper_chest")+value("mid_chest"),
    "back-width":value("lats"),"back-thickness":value("upper_back")+value("traps"),
    shoulders:value("front_delts")+value("side_delts")+value("rear_delts"),
    arms:value("biceps")+value("brachialis")+value("triceps"),
    quads:value("quads"),hamstrings:value("hamstrings"),glutes:value("glutes"),calves:value("calves"),
    core:value("abs")+value("obliques"),
  };
  const zone=getSessionZone(load);
  const ranked=Object.entries(scores).sort((a,b)=>b[1]-a[1]);
  const total=ranked.reduce((sum,[,amount])=>sum+amount,0);
  if(ranked[0]?.[1]>0&&ranked[0][1]>=total*.58)return ranked[0][0];
  if(zone==="upper"){
    const push=scores.chest+value("front_delts")+value("side_delts")+value("triceps");
    const pull=scores["back-width"]+scores["back-thickness"]+value("rear_delts")+value("biceps")+value("brachialis");
    if(push>pull*1.35)return "push";
    if(pull>push*1.35)return "pull";
    return "upper";
  }
  if(zone==="lower"){
    const anterior=scores.quads+value("adductors")*.4;
    const posterior=scores.hamstrings+scores.glutes+scores.calves*.25;
    if(anterior>posterior*1.2)return "legs-quads";
    if(posterior>anterior*1.2)return "legs-posterior";
    return "lower";
  }
  return "full-body";
}

function AnatomyAsset({side,assetKey}){
  const safeKey=ASSET_KEYS.has(assetKey)?assetKey:"full-body";
  const src=`${process.env.PUBLIC_URL||""}/images/anatomy/${safeKey}-${side}.webp`;
  return <div className={`premium-anatomy premium-anatomy--${side}`}>
    <img src={src} alt={side==="front"?"Anatomia frontal":"Anatomia posterior"} decoding="async"/>
    <small>{side==="front"?"FRENTE":"COSTAS"}</small>
  </div>
}

function MuscleSessionMap({items=[],exercises=[],focus=[],sessionLabel=""}){
  const load=buildSessionMuscles(items,exercises,focus);
  const zone=getSessionZone(load);
  const assetKey=getAnatomyAssetKey(load,sessionLabel);
  const ranked=Object.entries(load).sort((a,b)=>b[1]-a[1]).slice(0,5);
  return <div className="session-muscle-map" data-testid="session-muscle-map" data-zone={zone} data-asset={assetKey}>
    <div className="session-muscle-map__zone"><i/>{ZONE_LABEL[zone]}</div>
    <div className="session-muscle-map__views">
      <AnatomyAsset side="front" assetKey={assetKey}/>
      <AnatomyAsset side="back" assetKey={assetKey}/>
    </div>
    <div className="session-muscle-map__target-label">MÚSCULOS-ALVO</div>
    <div className="session-muscle-map__legend" aria-label="Músculos trabalhados hoje">
      {ranked.length?ranked.map(([id,value],i)=><span key={id} className={i===0?"primary":""}><i/>{LABELS[id]||id}{value>=1&&<small>{Math.round(value)}s</small>}</span>):<span><i/>Sessão geral</span>}
    </div>
  </div>
}

export default memo(MuscleSessionMap);
