const normalize=value=>String(value||"")
  .normalize("NFD").replace(/[\u0300-\u036f]/g,"")
  .toLowerCase().replace(/[^a-z0-9]+/g," ").trim();

const has=(key,...terms)=>terms.some(term=>key.includes(normalize(term)));

export const EXERCISE_ARTWORK_SPRITE="/images/reference/exercise-premium-sprite.webp";
export const EXERCISE_ARTWORK_TILE_COUNT=84;

export function artworkSlotForExercise(exercise={}){
  const key=normalize([
    exercise.id,exercise.exercise_id,exercise.name,
    exercise.primary_muscle,exercise.movement_pattern,
    ...(exercise.equipment||[]),
  ].join(" "));
  const primary=normalize(exercise.primary_muscle);
  const movement=normalize(exercise.movement_pattern);
  const equipment=(exercise.equipment||[]).map(normalize).join(" ");

  if(has(key,"supino inclinado","incline smith","db incline press","bb incline press")) return 1;
  if(has(key,"supino declinado","decline press")) return 2;
  if(has(key,"chest press","machine chest press")) return 3;
  if(has(key,"crucifixo com halter","db fly")) return 4;
  if(has(key,"crucifixo no cabo","cable fly","crossover","cross")) return 5;
  if(has(key,"peck deck")&&!has(key,"inverso")) return 6;
  if(has(key,"flexao de bracos","pushup","paralelas","dips")) return 7;
  if(has(key,"crucifixo inclinado","incline fly")) return 8;
  if(has(key,"pullover") && (primary.includes("chest")||has(key,"upper chest"))) return 9;
  if(has(key,"supino reto smith","smith bench press")) return 10;
  if(has(key,"supino reto com halter","db bench press")) return 11;
  if(primary.includes("chest")||has(key,"supino","bench press")) return 0;

  if(has(key,"barra fixa","pullup")) return 13;
  if(has(key,"remada curvada","bb row","supinated bb row")) return 14;
  if(has(key,"remada unilateral","db row")) return 15;
  if(has(key,"remada baixa","cable row","wide cable row","supinated cable row")) return 16;
  if(has(key,"cavalinho","t bar")) return 17;
  if(has(key,"remada apoiada","chest supported")) return 18;
  if(has(key,"puxada alta","pulldown","lat pulldown","neutral pulldown","supinated pulldown")) return 19;
  if(has(key,"puxada reta","straight arm","pulldown com corda")) return 20;
  if(has(key,"pullover","pull over maquina")) return 21;
  if(has(key,"levantamento terra","deadlift","rack pull","meio terra")) return 22;
  if(primary==="lats"||primary==="upper back"||primary==="upper_back") return 12;

  if(has(key,"arnold")) return 30;
  if(has(key,"desenvolvimento")||has(key,"ohp","shoulder press")){
    if(has(key,"halter","dumbbell")) return 25;
    if(has(key,"smith")) return 31;
    return 24;
  }
  if(has(key,"elevacao lateral","lateral raise")){
    if(has(key,"polia","cable")) return 35;
    return 26;
  }
  if(has(key,"elevacao frontal","front raise")) return 27;
  if(has(key,"elevacao posterior","rear delt")) return 28;
  if(has(key,"crucifixo inverso","reverse fly","rear fly","rear delt crossover")) return 29;
  if(has(key,"face pull")) return 32;
  if(has(key,"encolhimento","shrug")) return 33;
  if(has(key,"remada alta","upright row")) return 34;
  if(primary==="side delts"||primary==="side_delts") return 26;
  if(primary==="front delts"||primary==="front_delts") return 24;
  if(primary==="rear delts"||primary==="rear_delts") return 29;
  if(primary==="traps") return 33;

  if(primary==="biceps"||has(key,"rosca","curl")){
    if(has(key,"alternada")) return 37;
    if(has(key,"inclinada","incline")) return 38;
    if(has(key,"martelo","hammer")) return 39;
    if(has(key,"scott","preacher","spider")) return 40;
    if(has(key,"polia","cable","bayesian","corda","rope")) return 41;
    return 36;
  }
  if(primary==="triceps"||has(key,"triceps","pushdown","skullcrusher")){
    if(has(key,"testa","skull")) return 42;
    if(has(key,"corda","rope")) return 43;
    if(has(key,"frances","overhead")) return 44;
    if(has(key,"polia","pushdown","barra reta","pegada supinada")) return 45;
    if(has(key,"maquina","dip")) return 46;
    if(has(key,"coice","kickback")) return 47;
    return 43;
  }
  if(primary==="forearms"||has(key,"punho","wrist")) return 36;

  if(has(key,"hack squat")) return 50;
  if(has(key,"leg press")) return 49;
  if(has(key,"bulgaro","split squat")) return 51;
  if(has(key,"avanco","lunge")) return 52;
  if(has(key,"step up","passada")) return 53;
  if(has(key,"extensora","leg extension","knee extension")) return 54;
  if(has(key,"flexao de joelho sentado","seated hamstring curl","leg curl")) return 55;
  if(has(key,"stiff","rdl")) return 56;
  if(has(key,"terra romeno","romanian")) return 57;
  if(has(key,"mesa flexora","lying leg curl")) return 58;
  if(has(key,"panturrilha","calf")) return 59;
  if(has(key,"agachamento","squat","goblet")) return 48;
  if(primary==="quads") return 48;
  if(primary==="hamstrings") return 56;
  if(primary==="calves") return 59;

  if(has(key,"hip thrust","glute bridge")) return 60;
  if(has(key,"cadeira abdutora","abductor machine")) return 61;
  if(has(key,"coice na polia","cable glute kickback","gluteo na polia")) return 62;
  if(has(key,"quatro apoios","four point")) return 63;
  if(has(key,"gluteo no cabo")) return 64;
  if(has(key,"abdutora")) return 65;
  if(has(key,"bulgaro")) return 66;
  if(has(key,"step up")) return 67;
  if(has(key,"kickback")) return 68;
  if(has(key,"sumo")) return 69;
  if(has(key,"smith")&&primary==="glutes") return 70;
  if(has(key,"aducao","adutor","adduction")) return 71;
  if(primary==="glutes") return 60;
  if(primary==="adductors") return 71;

  if(has(key,"prancha lateral","side plank")) return 78;
  if(has(key,"prancha","plank")) return 72;
  if(has(key,"abdominal infra","reverse crunch")) return 74;
  if(has(key,"elevacao de pernas","leg raise")) return 75;
  if(has(key,"abdominal no cabo","cable crunch")) return 76;
  if(has(key,"woodchop","russian twist","rotacao","rotation")) return 77;
  if(has(key,"ab wheel","roda abdominal")) return 79;
  if(has(key,"abdominal maquina","machine crunch")) return 80;
  if(has(key,"infra no banco","decline crunch")) return 81;
  if(has(key,"toque no calcanhar","heel touch")) return 82;
  if(has(key,"mountain climber")) return 83;
  if(primary==="abs"||has(key,"abdominal","crunch")) return 73;

  const primaryFallback={upper_chest:1,mid_chest:0,lats:12,upper_back:18,front_delts:24,side_delts:26,rear_delts:29,traps:33,biceps:36,triceps:43,forearms:36,quads:48,hamstrings:56,glutes:60,adductors:71,calves:59,abs:73,erectors:22};
  if(Object.prototype.hasOwnProperty.call(primaryFallback,exercise.primary_muscle)) return primaryFallback[exercise.primary_muscle];
  if(movement.includes("press")) return 0;
  if(movement.includes("pull")) return 12;
  if(movement.includes("squat")||movement.includes("lunge")) return 48;
  if(movement.includes("hip")) return 60;
  if(movement.includes("flexion")||movement.includes("extension")) return equipment.includes("cable")?41:36;
  return -1;
}
