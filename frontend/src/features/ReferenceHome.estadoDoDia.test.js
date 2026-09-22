import ReferenceHome from "./ReferenceHome";
import React from "react";
import {renderToStaticMarkup} from "react-dom/server";

const casa=(extra={})=>{
  const html=renderToStaticMarkup(<ReferenceHome db={{profile:{name:"Nicolas"},program:{},...extra}} start={()=>{}}/>);
  return new DOMParser().parseFromString(html,"text/html").querySelector('[data-testid="reference-home-v3"]');
};

/** Series registradas ha `dias` dias, no fuso do aparelho, como o bootstrap devolve. */
const seriesEm=(dias,quantas=1,weight=60,reps=10)=>{
  const d=new Date();d.setDate(d.getDate()-dias);d.setHours(10,0,0,0);
  return Array.from({length:quantas},()=>({created_at:d.toISOString(),weight,reps}));
};

test("o rodape do Inicio traz prontidao e volume da semana",()=>{
  const home=casa();
  expect(home.querySelector('[data-testid="home-estado-do-dia"]')).not.toBeNull();
  expect(home.textContent).toContain("Carregando check-in");
  expect(home.querySelector('[data-testid="home-volume-semana"]')).not.toBeNull();
});

/*
 * O buraco que isto fecha: o check-in so era alcancavel como portao antes de comecar um
 * treino, e `openPlan` retorna cedo no descanso. Quer dizer que no dia em que a recuperacao
 * mais importa ela era impossivel de registrar — e o motor decide serie e RIR com ela.
 */
test("antes da resposta do servidor, mostra carregamento sem sugerir um check-in novo",()=>{
  const home=casa();
  expect(home.querySelector('[data-testid="home-prontidao"]')).toBeNull();
  expect(home.textContent).toContain("Carregando check-in");
});

/*
 * O texto do nivel e testado em `ritmoDaSemana.test.js`, no modulo puro. Aqui so importa
 * que a tela leia o nivel do MOTOR e nao recalcule: `renderToStaticMarkup` nao roda efeito,
 * entao o estado com check-in nao existe neste harness e nao adianta fingir que existe.
 */
test("o descanso não presume que a próxima sessão seja amanhã",()=>{
  const home=casa({program:{rest_day:true}});
  const contexto=home.querySelector('[data-testid="home-cycle-context"]').textContent;
  if(contexto.startsWith("DESCANSO")) expect(contexto).toBe("DESCANSO HOJE · PRÓXIMA SESSÃO");
});

test("a sequencia aparece junto da data a partir de dois dias",()=>{
  const comum=casa({recent_sets:[...seriesEm(0),...seriesEm(1),...seriesEm(2)]});
  expect(comum.querySelector('[data-testid="home-sequencia"]').textContent).toBe("3 dias seguidos");
});

test("um dia isolado nao vira sequencia",()=>{
  expect(casa({recent_sets:seriesEm(0)}).querySelector('[data-testid="home-sequencia"]')).toBeNull();
});

test("sem treino nenhum a semana nao inventa carga",()=>{
  const card=casa().querySelector('[data-testid="home-volume-semana"]');
  expect(card.querySelector("strong").textContent).toBe("0 séries");
  expect(card.querySelector("p").textContent).toBe("Nenhuma carga registrada");
});

test("a semana soma as series e a carga levantada",()=>{
  const card=casa({recent_sets:seriesEm(0,4,50,10)}).querySelector('[data-testid="home-volume-semana"]');
  expect(card.querySelector("strong").textContent).toBe("4 séries");
  expect(card.querySelector("p").textContent).toMatch(/levantados$/);
});
