import {planoDaUrl, irParaALanding, PLANOS, CHAVE_DO_DESVIO} from "./entradaPelaLanding";

/*
 * A landing nova e um pacote separado, servido pelo nginx na raiz. O aplicativo responde
 * por /login, /assinar e /app. Estes testes prendem a travessia entre os dois:
 *
 *   1. o plano escolhido na landing chega pela URL e nada mais viaja por ali;
 *   2. o aplicativo, se cair na raiz por navegacao interna, carrega a landing de verdade
 *      em vez de desenhar a pagina de venda antiga.
 */

// -- O plano que vem da landing --------------------------------------------------------

test.each(PLANOS)("%s chega pela URL",(code)=>{
  expect(planoDaUrl(`?plano=${code}`)).toBe(code);
});

test("aceita maiuscula e espaco, que e o que um link colado traz",()=>{
  expect(planoDaUrl("?plano=PRO")).toBe("pro");
  expect(planoDaUrl("?plano= elite ")).toBe("elite");
});

test.each([
  ["codigo que nao existe", "?plano=premium"],
  ["vazio", "?plano="],
  ["sem o parametro", "?outra=coisa"],
  ["busca vazia", ""],
  ["tentativa de injecao", "?plano=<script>"],
])("%s nao preseleciona plano nenhum",(_,busca)=>{
  // Sem plano valido o cadastro mostra a lista, que e o comportamento de sempre.
  expect(planoDaUrl(busca)).toBe("");
});

test("preco e periodicidade NAO viajam pela URL",()=>{
  // O navegador manda so o codigo. Preco e frequencia saem da allow-list do servidor, e
  // e por isso que um link adulterado nao consegue comprar mais barato.
  expect(planoDaUrl("?plano=pro&preco=1&frequencia=anual")).toBe("pro");
});

test("os codigos sao os mesmos do backend",()=>{
  expect(PLANOS).toEqual(["essential","pro","elite"]);
});

// -- A volta para a landing ------------------------------------------------------------

const janelaFalsa=()=>{
  const guardado={};
  return {
    location:{replace:jest.fn()},
    sessionStorage:{
      getItem:k=>(k in guardado?guardado[k]:null),
      setItem:(k,v)=>{guardado[k]=String(v)},
    },
  };
};

test("cair na raiz carrega a landing de verdade",()=>{
  const j=janelaFalsa();
  expect(irParaALanding(j)).toBe(true);
  expect(j.location.replace).toHaveBeenCalledWith("/");
});

test("so desvia uma vez por sessao",()=>{
  // Em producao nao ha laco, porque / devolve HTML estatico e o React nem monta. A trava
  // existe para o ambiente local, onde servir o aplicativo na raiz travaria o navegador.
  const j=janelaFalsa();
  expect(irParaALanding(j)).toBe(true);
  expect(irParaALanding(j)).toBe(false);
  expect(irParaALanding(j)).toBe(false);
  expect(j.location.replace).toHaveBeenCalledTimes(1);
});

test("marca a sessao com a chave combinada",()=>{
  const j=janelaFalsa();
  irParaALanding(j);
  expect(j.sessionStorage.getItem(CHAVE_DO_DESVIO)).toBe("1");
});

test("armazenamento bloqueado nao impede a saida",()=>{
  // Aba anonima ou cookies bloqueados: o desvio importa mais que a trava.
  const j={
    location:{replace:jest.fn()},
    sessionStorage:{getItem(){throw new Error("bloqueado")},setItem(){throw new Error("bloqueado")}},
  };
  expect(()=>irParaALanding(j)).not.toThrow();
  expect(j.location.replace).toHaveBeenCalledWith("/");
});
