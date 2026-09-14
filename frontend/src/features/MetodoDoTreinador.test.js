import React,{act} from "react";
import {createRoot} from "react-dom/client";
import MetodoDoTreinador from "./MetodoDoTreinador";

const refeicao=(papel,nome,carbo,semCarbo=false)=>({
  papel,nome,porque:`Porque ${nome} serve para isso.`,carbo_g:carbo,sem_carbo:semCarbo,
  carbo:semCarbo?["Arroz branco cozido"]:["Aveia em flocos"],
  proteina:["Peito de frango grelhado","Carne bovina grelhada (patinho)"],
  gordura:papel==="almoco"?["Azeite de oliva"]:[],
  acompanha:papel==="almoco"?["Alface","Tomate"]:[],
});

const metodo=(hoje=null)=>({
  hoje,classe:null,
  formatos:{
    low:{rotulo:"Dia low",resumo:"Sem amido no pós-treino.",carbo_g:300,
         refeicoes:[refeicao("pre_treino","Pré-treino",90),
                    refeicao("pos_treino","Pós-treino",0,true),
                    refeicao("almoco","Almoço",0,true),
                    refeicao("jantar","Jantar",30)]},
    high:{rotulo:"Dia high",resumo:"O amido volta.",carbo_g:440,
          refeicoes:[refeicao("pre_treino","Pré-treino",132),
                     refeicao("pos_treino","Pós-treino",97),
                     refeicao("almoco","Almoço",97),
                     refeicao("jantar","Jantar",22)]},
  },
  regras:[{chave:"pesagem",regra:"Todos os alimentos são pesados já prontos.",
           porque:"É como a tabela nutricional mede."},
          {chave:"agua",regra:"Mínimo de 4 litros de água por dia.",
           porque:"Aparece em todos os protocolos."}],
  protocolos:[{chave:"3low1high",nome:"3 low, 1 high",para_quem:"Corte com recarga frequente."}],
});

let host,root;
beforeEach(()=>{global.IS_REACT_ACT_ENVIRONMENT=true;host=document.createElement("div");document.body.appendChild(host);root=createRoot(host);});
afterEach(()=>{act(()=>root.unmount());host.remove();});
const render=el=>act(()=>{root.render(el)});
const abrir=()=>act(()=>{host.querySelector(".metodo-topo").click()});
const abas=()=>[...host.querySelectorAll(".metodo-aba")];
const refeicoes=()=>[...host.querySelectorAll(".metodo-refeicao")];

test("sem metodo o bloco nao aparece, em vez de renderizar vazio",()=>{
  render(<MetodoDoTreinador metodo={null}/>);
  expect(host.querySelector('[data-testid="metodo-do-treinador"]')).toBeNull();
});

test("comeca fechado: o plano do dia e o que a pessoa abre todo dia",()=>{
  render(<MetodoDoTreinador metodo={metodo()}/>);
  expect(host.querySelector('[data-testid="metodo-do-treinador"]')).not.toBeNull();
  expect(host.querySelector(".metodo-corpo")).toBeNull();
  expect(host.querySelector(".metodo-topo").getAttribute("aria-expanded")).toBe("false");
});

test("aberto, mostra as refeicoes do dia na ordem do metodo",()=>{
  render(<MetodoDoTreinador metodo={metodo()}/>);
  abrir();
  expect(refeicoes().map(li=>li.querySelector("strong").textContent))
    .toEqual(["Pré-treino","Pós-treino","Almoço","Jantar"]);
});

// "0 g" parece defeito. A refeicao que perde o amido tem que dizer isso com palavra.
test("a refeicao sem amido diz sem amido, e nao zero grama",()=>{
  render(<MetodoDoTreinador metodo={metodo()}/>);
  abrir();
  const pos=refeicoes()[1];
  expect(pos.querySelector(".metodo-gramas").textContent).toBe("sem amido");
  expect(pos.className).toContain("metodo-sem-amido");
});

// Listar a fonte de carboidrato de uma refeicao que hoje nao tem carboidrato seria convite
// para a pessoa comer justamente o que o dia low tira.
test("a refeicao sem amido nao lista fonte de carboidrato",()=>{
  render(<MetodoDoTreinador metodo={metodo()}/>);
  abrir();
  const pos=refeicoes()[1].textContent;
  expect(pos).not.toContain("Arroz branco");
  expect(pos).toContain("Peito de frango");
});

test("as fontes aparecem como alternativa, com ou, e nao como lista de ingredientes",()=>{
  render(<MetodoDoTreinador metodo={metodo()}/>);
  abrir();
  expect(refeicoes()[0].textContent).toContain("Peito de frango grelhado ou Carne bovina grelhada (patinho)");
});

test("trocar de aba troca os numeros do dia",()=>{
  render(<MetodoDoTreinador metodo={metodo()}/>);
  abrir();
  expect(host.querySelector(".metodo-total").textContent).toContain("300 g");
  act(()=>{abas()[1].click()});
  expect(host.querySelector(".metodo-total").textContent).toContain("440 g");
  expect(refeicoes()[1].querySelector(".metodo-gramas").textContent).toBe("97 g");
});

test("o formato de hoje ja abre selecionado e marcado",()=>{
  render(<MetodoDoTreinador metodo={metodo("high")}/>);
  abrir();
  expect(abas()[1].getAttribute("aria-selected")).toBe("true");
  expect(abas()[1].querySelector("em").textContent).toBe("hoje");
  expect(abas()[0].querySelector("em")).toBeNull();
  expect(host.querySelector(".metodo-total").textContent).toContain("Hoje são");
});

// Em dia de descanso o treinador nao escreveu formato. O bloco mostra a referencia sem
// afirmar que um dos dois e o de hoje.
test("em dia sem formato escrito, nenhuma aba e marcada como hoje",()=>{
  render(<MetodoDoTreinador metodo={metodo(null)}/>);
  abrir();
  expect(host.querySelectorAll(".metodo-aba em")).toHaveLength(0);
  expect(abas()[0].getAttribute("aria-selected")).toBe("true");
  expect(host.querySelector(".metodo-total").textContent).toContain("Neste formato");
});

test("cada regra chega com a razao junto",()=>{
  render(<MetodoDoTreinador metodo={metodo()}/>);
  abrir();
  const itens=[...host.querySelectorAll('[data-testid="metodo-regras"] li')];
  expect(itens).toHaveLength(2);
  expect(itens[0].textContent).toContain("pesados já prontos");
  expect(itens[0].textContent).toContain("tabela nutricional mede");
});

test("fecha de novo no segundo toque",()=>{
  render(<MetodoDoTreinador metodo={metodo()}/>);
  abrir();
  abrir();
  expect(host.querySelector(".metodo-corpo")).toBeNull();
});

// A ceia e so proteina lenta: ela nunca teve carboidrato. "0 g" ali pareceria defeito, e
// nao a natureza da refeicao.
test("refeicao que nunca teve carboidrato nao mostra grama nenhuma",()=>{
  const m=metodo();
  const ceia={papel:"ceia",nome:"Ceia",porque:"Proteína lenta.",carbo_g:0,sem_carbo:false,
              carbo:[],proteina:["Clara de ovo","Ovo inteiro"],gordura:[],acompanha:[]};
  m.formatos.low.refeicoes=[...m.formatos.low.refeicoes,ceia];
  render(<MetodoDoTreinador metodo={m}/>);
  abrir();
  const ultima=refeicoes()[refeicoes().length-1];
  expect(ultima.querySelector("strong").textContent).toBe("Ceia");
  expect(ultima.querySelector(".metodo-gramas")).toBeNull();
  expect(ultima.textContent).not.toContain("0 g");
  expect(ultima.textContent).toContain("Clara de ovo");
});
