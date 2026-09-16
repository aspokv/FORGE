import {ehSessaoExpirada, anunciarSessaoExpirada, limparAviso, sessaoExpirouAgora,
        CHAVE_DO_AVISO, EVENTO, AVISO} from "./sessaoExpirada";

/*
 * O defeito que isto conserta, na tela de treino do atleta:
 *
 *     "Não foi possível confirmar o estado da sessão."   [Tentar novamente]
 *
 * O token do FORGE vale 12 horas e nao e renovado. Quem deixa o aplicativo aberto de um dia
 * para o outro passa a tomar 401 em toda requisicao — e o backend responde certo,
 * `401 {"detail": "Sessão expirada"}`. Faltava o front OUVIR: havia interceptor de
 * requisicao e nenhum de resposta, entao a sessao vencida virava um erro generico em cada
 * tela, com um "Tentar novamente" que nunca poderia funcionar.
 */

const erro = (status, url = "/api/workout/completion") =>
  ({response: {status}, config: {url}});

beforeEach(() => { limparAviso(); window.localStorage.clear(); });

// -- O que conta como sessao vencida ---------------------------------------------------

test("401 com token na mao e sessao vencida",()=>{
  expect(ehSessaoExpirada(erro(401), true)).toBe(true);
});

test("401 SEM token nao e sessao vencida",()=>{
  // Sem token nao existe sessao para vencer: e rota protegida aberta sem login, e o
  // roteador ja manda para a entrada.
  expect(ehSessaoExpirada(erro(401), false)).toBe(false);
});

test.each([[400],[402],[403],[404],[422],[500],[502]])(
  "%i nao e sessao vencida",(status)=>{
    expect(ehSessaoExpirada(erro(status), true)).toBe(false);
  });

test("erro de rede, sem resposta, nao desloga ninguem",()=>{
  // Foi por confundir os dois que a tela de treino sumia num tropeco de conexao.
  expect(ehSessaoExpirada(new Error("Network Error"), true)).toBe(false);
  expect(ehSessaoExpirada(undefined, true)).toBe(false);
  expect(ehSessaoExpirada({}, true)).toBe(false);
});

test.each([
  ["/api/auth/login"],
  ["/api/auth/signup"],
  ["/api/auth/recuperar"],
  ["/api/auth/invite/abc"],
])("401 em %s e senha errada, e nao sessao vencida",(url)=>{
  // Deslogar aqui criaria um laco: erra a senha, e deslogado, volta para o login.
  expect(ehSessaoExpirada(erro(401, url), true)).toBe(false);
});

test("le a url tambem de response.config, que e onde o axios as vezes poe",()=>{
  const e = {response: {status: 401, config: {url: "/api/auth/login"}}};
  expect(ehSessaoExpirada(e, true)).toBe(false);
});

// -- O anuncio -------------------------------------------------------------------------

test("anuncia uma vez e dispara o evento",()=>{
  const ouvinte = jest.fn();
  window.addEventListener(EVENTO, ouvinte);
  expect(anunciarSessaoExpirada()).toBe(true);
  expect(ouvinte).toHaveBeenCalledTimes(1);
  expect(window.localStorage.getItem(CHAVE_DO_AVISO)).toBe("1");
  window.removeEventListener(EVENTO, ouvinte);
});

test("cinco chamadas falhando anunciam UMA saida",()=>{
  // Uma tela faz varias chamadas ao abrir. Sem a trava seriam cinco saidas e cinco
  // navegacoes.
  const ouvinte = jest.fn();
  window.addEventListener(EVENTO, ouvinte);
  for (let i = 0; i < 5; i++) anunciarSessaoExpirada();
  expect(ouvinte).toHaveBeenCalledTimes(1);
  window.removeEventListener(EVENTO, ouvinte);
});

test("entrar de novo solta a trava",()=>{
  anunciarSessaoExpirada();
  limparAviso();
  expect(sessaoExpirouAgora()).toBe(false);
  const ouvinte = jest.fn();
  window.addEventListener(EVENTO, ouvinte);
  expect(anunciarSessaoExpirada()).toBe(true);
  expect(ouvinte).toHaveBeenCalledTimes(1);
  window.removeEventListener(EVENTO, ouvinte);
});

// -- O aviso na tela de entrada ---------------------------------------------------------

test("a tela de entrada consegue saber que a sessao venceu",()=>{
  expect(sessaoExpirouAgora()).toBe(false);
  anunciarSessaoExpirada();
  expect(sessaoExpirouAgora()).toBe(true);
});

test("o aviso explica e nao acusa",()=>{
  // Quem ficou 12 horas logado nao errou nada; o texto precisa dizer o que aconteceu e
  // que nada foi perdido.
  expect(AVISO).toMatch(/expirou/i);
  expect(AVISO).toMatch(/entre de novo/i);
  expect(AVISO).not.toMatch(/erro|inválid|falhou/i);
});

// -- Armazenamento bloqueado ------------------------------------------------------------

test("armazenamento bloqueado nao impede a saida",()=>{
  // Aba anonima, cookies bloqueados: localStorage lanca. A saida importa mais que o aviso.
  const ouvinte = jest.fn();
  const janela = {
    localStorage: {setItem(){throw new Error("bloqueado")}, removeItem(){throw new Error("bloqueado")},
                   getItem(){throw new Error("bloqueado")}},
    dispatchEvent: ouvinte,
    Event: window.Event,
  };
  expect(() => anunciarSessaoExpirada(janela)).not.toThrow();
  expect(ouvinte).toHaveBeenCalled();
  expect(sessaoExpirouAgora(janela)).toBe(false);
});
