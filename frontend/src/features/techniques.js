// Fallback catalog when backend techniques not yet loaded.
export const TECHNIQUE_FALLBACK = [
  {id:"straight",name:"Straight Sets",short:"Séries retas",fatigue:"baixa",description:"Todas as séries com o mesmo peso e faixa de reps, respeitando o RIR planejado.",protocol:"Peso fixo. Ex.: 3×8 @ RIR 2.",when:"Base do plano; não substitua sem motivo."},
  {id:"drop-set",name:"Drop Set",short:"Redução de carga sem descanso",fatigue:"alta",description:"Depois da última série efetiva, reduza 20–30% da carga e continue até nova falha técnica.",protocol:"Série principal → −25% carga → ao fim, opcional novo −20%.",when:"1–2 exercícios por sessão, em músculo prioritário."},
  {id:"mechanical-drop-set",name:"Mechanical Drop Set",short:"Redução por biomecânica",fatigue:"alta",description:"Mantém a carga; muda a posição/pegada para uma mais forte quando falhar.",protocol:"Ex.: elevação lateral halter posição forte → seguir até nova falha.",when:"Ombro lateral, bíceps, panturrilha."},
  {id:"rest-pause",name:"Rest-Pause",short:"Pausas curtas com mesma carga",fatigue:"alta",description:"Chegue perto da falha, descanse 10–20 s e retome. 2–3 pausas.",protocol:"Ex.: 8 reps → 15 s → 3 reps → 15 s → 2 reps.",when:"Fim do exercício; mantém intensidade."},
  {id:"myo-reps",name:"Myo-Reps",short:"Ativação + mini-séries",fatigue:"alta",description:"Série de ativação até próximo da falha, seguida de mini-séries de 3–5 reps com pausas curtíssimas.",protocol:"Ex.: 12 reps @ RIR 0–1 → 5 s → 4 reps → 5 s → 4 reps → 5 s → 3 reps.",when:"Alta densidade em máquinas e cabos."},
  {id:"cluster",name:"Cluster Set",short:"Blocos com micro-pausas",fatigue:"moderada",description:"Divide a série em blocos com 10–20 s de pausa para manter carga alta com menos fadiga por rep.",protocol:"Ex.: 4+4+4 @ 85% 1RM com 15 s entre blocos.",when:"Força ou densidade em compostos."},
  {id:"top-set-backoff",name:"Top Set + Back-off",short:"Pico + volume",fatigue:"moderada",description:"Uma série pesada no topo, seguida de séries de volume com carga reduzida.",protocol:"Ex.: 1×5 @ RIR 1 → 3×8 com −15% de carga.",when:"Compostos principais com estímulo pesado."},
  {id:"pyramid",name:"Pyramid",short:"Escadas de carga",fatigue:"moderada",description:"Aumenta ou reduz progressivamente carga e reps ao longo das séries.",protocol:"Ex.: 12 → 10 → 8 → 6 subindo a carga.",when:"Aquecimento e aprendizado de esforço."},
  {id:"lengthened-partials",name:"Lengthened Partials",short:"Parciais no alongamento",fatigue:"moderada",description:"Ao chegar próximo da falha na amplitude completa, continue com parciais na porção alongada.",protocol:"Ex.: 10 completas + 5 parciais na metade baixa.",when:"Exercícios com sobrecarga no alongamento."},
  {id:"superset",name:"Superset",short:"Dois exercícios seguidos",fatigue:"moderada",description:"Executa dois exercícios em sequência sem descanso.",protocol:"Ex.: Rosca direta + Tríceps corda, 3 rounds.",when:"Densidade; evite em compostos exigentes."},
];

export const findTechnique = (list, id, name) => {
  const catalog = list && list.length ? list : TECHNIQUE_FALLBACK;
  return catalog.find(t => t.id === id) || catalog.find(t => t.name === name) || catalog[0];
};
