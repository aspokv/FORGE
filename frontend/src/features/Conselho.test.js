import {act} from "react";
import {createRoot} from "react-dom/client";
import Conselho from "./Conselho";

/*
 * A tela do Conselho.
 *
 * O que estes testes prendem nao e o desenho, e as tres regras que a interface herda das
 * travas do motor:
 *
 *   1. quando NAO existe mudanca, nao existe botao de aplicar. A tela nao inventa uma
 *      acao para parecer util;
 *   2. "Agora nao" existe sempre que "Aplicar" existe, porque quem conhece o contexto
 *      que o banco nao tem e a pessoa;
 *   3. um 402 vira convite, e nunca o detalhe cru da API: em 402 o `detail` e um OBJETO,
 *      e renderizar objeto derruba a tela inteira.
 *
 * Sem `@testing-library`: o projeto nao a tem instalada, e `react-dom/client` com `act`
 * da o mesmo resultado sem dependencia nova.
 */

const RESPOSTA_DE_CORTE={
  semana:"2026-S12",
  decisao:{
    alavanca:"caloria",
    titulo:"Agora sim, o corte e seu",
    motivo:"Leitura limpa: voce registrou 7 de 7 dias e seu treino nao caiu.",
    mudanca:{tipo:"kcal",de:2000,para:1840,delta:-160,
             trava:"proteina fixa em gramas e piso de gordura preservado"},
    previsao:{tipo:"ritmo_de_peso",frase:"seu peso cai entre 0,27 e 0,90 kg por semana"},
  },
  aplicada:null,
  estado:{
    comida:{dias_registrados:7,janela_dias:7,kcal_media:2000},
    peso:{suficiente:true,kg_por_semana:-0.02,dias_cobertos:22},
    volume:{suficiente:true,variacao:0,series_agora:20,series_base:20},
    prontidao:{suficiente:true,pior_dia:"terca",pior_pontuacao:2.5},
  },
  placar_anterior:{resultado:"errou",previsto:"seu peso cai 0,4 kg"},
  retrospecto:{acertos:3,erros:1,julgadas:4,taxa:0.75},
};

const SEM_MUDANCA={
  semana:"2026-S12",
  decisao:{alavanca:"aderencia",titulo:"Nao vou mexer no seu plano",
           motivo:"Voce registrou 2 de 7 dias.",mudanca:null,
           previsao:{frase:"voce registra pelo menos 6 dias"}},
  aplicada:null,
  estado:{comida:{dias_registrados:2,janela_dias:7},peso:{suficiente:false},
          volume:{suficiente:false},prontidao:{suficiente:false}},
  placar_anterior:null,
  retrospecto:{acertos:0,erros:0,julgadas:0,taxa:null},
};

function clienteFalso(resposta,{status=200,aoAplicar}={}){
  const chamadas={get:0,post:[]};
  return {
    chamadas,
    get:jest.fn(async()=>{
      chamadas.get+=1;
      if(status!==200){
        const erro=new Error("bloqueado");
        erro.response={status,data:{detail:{capability:"advanced_analytics"}}};
        throw erro;
      }
      return {data:typeof resposta==="function"?resposta(chamadas.get):resposta};
    }),
    post:jest.fn(async(url,corpo)=>{
      chamadas.post.push(corpo);
      return {data:aoAplicar||{status:"aplicada"}};
    }),
  };
}

async function montar(cliente){
  const alvo=document.createElement("div");
  document.body.appendChild(alvo);
  const root=createRoot(alvo);
  await act(async()=>{root.render(<Conselho API="/api" axiosCliente={cliente}/>)});
  return {alvo,root,desmontar:()=>act(()=>root.unmount())};
}

afterEach(()=>{document.body.innerHTML=""});

test("mostra o veredito, o motivo e a mudanca proposta",async()=>{
  const {alvo,desmontar}=await montar(clienteFalso(RESPOSTA_DE_CORTE));
  expect(alvo.textContent).toContain("Agora sim, o corte e seu");
  expect(alvo.textContent).toContain("7 de 7 dias");
  expect(alvo.textContent).toContain("1840 kcal");
  desmontar();
});

test("a previsao aparece, porque e a aposta que o motor faz",async()=>{
  const {alvo,desmontar}=await montar(clienteFalso(RESPOSTA_DE_CORTE));
  expect(alvo.querySelector('[data-testid="conselho-previsao"]').textContent)
    .toContain("seu peso cai entre 0,27 e 0,90 kg por semana");
  desmontar();
});

test("a leitura que gerou o veredito viaja junto",async()=>{
  // Um veredito sem os numeros e um palpite com tipografia bonita.
  const {alvo,desmontar}=await montar(clienteFalso(RESPOSTA_DE_CORTE));
  const leitura=alvo.querySelector('[data-testid="conselho-leitura"]').textContent;
  expect(leitura).toContain("7/7");
  expect(leitura).toContain("terca");
  desmontar();
});

test("o placar mostra quando o motor ERROU",async()=>{
  // Um conselho que nunca pode estar errado nao e um conselho.
  const {alvo,desmontar}=await montar(clienteFalso(RESPOSTA_DE_CORTE));
  const placar=alvo.querySelector('[data-testid="conselho-placar"]').textContent;
  expect(placar).toContain("errei");
  expect(placar).toContain("3 de 4");
  desmontar();
});

test("sem mudanca proposta nao existe botao de aplicar",async()=>{
  const {alvo,desmontar}=await montar(clienteFalso(SEM_MUDANCA));
  expect(alvo.textContent).toContain("Nao vou mexer no seu plano");
  expect(alvo.querySelector('[data-testid="conselho-aplicar"]')).toBeNull();
  expect(alvo.querySelector('[data-testid="conselho-mudanca"]')).toBeNull();
  desmontar();
});

test("recusar tem o mesmo lugar que aplicar",async()=>{
  const {alvo,desmontar}=await montar(clienteFalso(RESPOSTA_DE_CORTE));
  expect(alvo.querySelector('[data-testid="conselho-aplicar"]')).not.toBeNull();
  expect(alvo.querySelector('[data-testid="conselho-recusar"]')).not.toBeNull();
  desmontar();
});

test("aplicar envia aceitar verdadeiro e recarrega a semana",async()=>{
  const cliente=clienteFalso(RESPOSTA_DE_CORTE);
  const {alvo,desmontar}=await montar(cliente);
  await act(async()=>{
    alvo.querySelector('[data-testid="conselho-aplicar"]').click();
  });
  expect(cliente.chamadas.post).toEqual([{aceitar:true}]);
  expect(cliente.chamadas.get).toBe(2);   // busca de novo para mostrar o estado novo
  desmontar();
});

test("recusar envia aceitar falso",async()=>{
  const cliente=clienteFalso(RESPOSTA_DE_CORTE,{aoAplicar:{status:"recusada"}});
  const {alvo,desmontar}=await montar(cliente);
  await act(async()=>{
    alvo.querySelector('[data-testid="conselho-recusar"]').click();
  });
  expect(cliente.chamadas.post).toEqual([{aceitar:false}]);
  desmontar();
});

test("quem ja respondeu ve o que ficou decidido, e nao os botoes de novo",async()=>{
  const respondido={...RESPOSTA_DE_CORTE,
    aplicada:{status:"aplicada",de:2000,para:1840}};
  const {alvo,desmontar}=await montar(clienteFalso(respondido));
  expect(alvo.querySelector('[data-testid="conselho-aplicar"]')).toBeNull();
  expect(alvo.querySelector('[data-testid="conselho-resolvido"]').textContent)
    .toContain("1840 kcal");
  desmontar();
});

test("um 402 vira convite, e nunca o objeto cru da API",async()=>{
  // Renderizar `detail` em 402 derrubaria a tela: ele e um objeto, nao um texto.
  const {alvo,desmontar}=await montar(clienteFalso(null,{status:402}));
  expect(alvo.querySelector('[data-testid="conselho-bloqueado"]')).not.toBeNull();
  expect(alvo.textContent).toContain("FORGE Elite");
  expect(alvo.textContent).not.toContain("advanced_analytics");
  desmontar();
});

test("erro de rede nao derruba a tela e oferece nova tentativa",async()=>{
  const {alvo,desmontar}=await montar(clienteFalso(null,{status:500}));
  expect(alvo.textContent).toContain("Não consegui ler sua semana");
  desmontar();
});

test("os numeros da leitura usam virgula, como o resto das frases",async()=>{
  // A tela mostrava "seu peso cai entre 0,28 kg" na frase e "0.00 kg" no quadro logo
  // abaixo, porque `toFixed` devolve ponto. Duas grafias na mesma tela denunciam
  // que o texto foi montado por maquina.
  const {alvo,desmontar}=await montar(clienteFalso(RESPOSTA_DE_CORTE));
  const leitura=alvo.querySelector('[data-testid="conselho-leitura"]').textContent;
  expect(leitura).toContain("-0,02 kg");
  expect(leitura).not.toMatch(/\d\.\d/);
  desmontar();
});
