/**
 * A sessão que venceu com o aplicativo aberto.
 *
 * O token do FORGE vale 12 horas e não é renovado. Quem deixa o aplicativo aberto de um dia
 * para o outro — que é exatamente o que um atleta faz — passa a receber 401 em TODA
 * requisição. O backend responde certo e claro:
 *
 *     401 {"detail": "Sessão expirada"}
 *
 * Só que o front tinha interceptor de REQUISIÇÃO (que anexa o token) e nenhum de RESPOSTA.
 * O token só era limpo quando o aplicativo carregava do zero. Então a sessão vencida virava
 * um erro genérico em cada tela, com um botão "Tentar novamente" que NUNCA poderia
 * funcionar — foi assim que apareceu, na tela de treino:
 *
 *     "Não foi possível confirmar o estado da sessão."  [Tentar novamente]
 *
 * O atleta não tinha como saber que precisava sair e entrar de novo.
 *
 * Este módulo é a decisão: o que conta como sessão vencida, e o que não conta.
 */

/** Rotas onde 401 significa "credencial errada", e não "sua sessão venceu". */
const ROTAS_DE_ENTRADA = /\/auth\/(login|signup|register|recuperar|reset|invite)/i;

/**
 * Este erro é uma sessão vencida?
 *
 * `temToken` é injetado para o teste não depender de localStorage — e porque sem token não
 * existe sessão para vencer: um 401 ali é uma rota protegida acessada sem login, e o
 * roteador já trata isso.
 */
export function ehSessaoExpirada(erro, temToken) {
  if (erro?.response?.status !== 401) return false;
  if (!temToken) return false;
  // Deslogar no 401 do próprio login criaria um laço: erra a senha, é deslogado, é mandado
  // para o login, erra de novo.
  const url = String(erro?.config?.url || erro?.response?.config?.url || "");
  if (ROTAS_DE_ENTRADA.test(url)) return false;
  return true;
}

export const CHAVE_DO_AVISO = "forge_sessao_expirada";
export const EVENTO = "forge:sessao-expirada";

/**
 * Anuncia a sessão vencida uma única vez.
 *
 * Uma tela faz cinco chamadas ao abrir; sem esta trava, um token vencido dispararia cinco
 * saídas e cinco navegações. A trava é solta assim que alguém entra de novo.
 */
let jaAnunciou = false;

export function anunciarSessaoExpirada(janela = window) {
  if (jaAnunciou) return false;
  jaAnunciou = true;
  try {
    janela.localStorage.setItem(CHAVE_DO_AVISO, "1");
  } catch {
    /* armazenamento bloqueado não pode impedir a saída */
  }
  janela.dispatchEvent(new janela.Event(EVENTO));
  return true;
}

export function limparAviso(janela = window) {
  jaAnunciou = false;
  try {
    janela.localStorage.removeItem(CHAVE_DO_AVISO);
  } catch {
    /* idem */
  }
}

/** A tela de entrada pergunta isto para explicar por que a pessoa está ali. */
export function sessaoExpirouAgora(janela = window) {
  try {
    return janela.localStorage.getItem(CHAVE_DO_AVISO) === "1";
  } catch {
    return false;
  }
}

export const AVISO =
  "Sua sessão expirou por segurança. Entre de novo para continuar de onde parou.";
