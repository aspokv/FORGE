/**
 * A fronteira entre a landing e o aplicativo.
 *
 * A partir da landing nova, `/` deixou de ser do aplicativo: e um pacote separado (Vite),
 * servido pelo nginx, e o aplicativo (CRA) responde por `/login`, `/assinar`, `/app` e o
 * resto. Duas coisas precisam atravessar essa fronteira, e as duas moram aqui para poderem
 * ser testadas sem montar a aplicação inteira.
 */

/** Os únicos códigos de plano que existem, iguais aos de `backend/billing_plans.py`. */
export const PLANOS = ["essential", "pro", "elite"];

/**
 * O plano que a pessoa escolheu na landing, lido da URL: `/assinar?plano=pro`.
 *
 * Qualquer valor fora da lista vira string vazia, e o cadastro mostra a lista de planos
 * como sempre fez. Nada de preço ou periodicidade viaja por aqui: o navegador manda só o
 * código, e a allow-list do servidor decide o resto.
 */
export function planoDaUrl(busca) {
  try {
    const params = new URLSearchParams(
      busca !== undefined ? busca : window.location.search);
    const code = (params.get("plano") || "").trim().toLowerCase();
    return PLANOS.includes(code) ? code : "";
  } catch {
    return "";
  }
}

export const CHAVE_DO_DESVIO = "forge_landing_redirect";

/**
 * Sair do aplicativo e carregar a landing de verdade.
 *
 * O aplicativo ainda pode CHEGAR em `/` por navegação interna: o desvio de quem não está
 * logado manda para `/`, e cancelar o cadastro também. Nesses casos desenhar a página de
 * venda antiga seria mostrar um produto que não existe mais, então a saída é carregar a
 * página real.
 *
 * Não existe laço em produção, porque `/` devolve HTML estático e o React do aplicativo
 * nem chega a montar. A trava de sessão cobre o caso de alguém servir o aplicativo na raiz
 * num ambiente local, onde o laço seria possível e travaria o navegador.
 */
export function irParaALanding(janela = window) {
  try {
    if (janela.sessionStorage.getItem(CHAVE_DO_DESVIO) === "1") return false;
    janela.sessionStorage.setItem(CHAVE_DO_DESVIO, "1");
  } catch {
    /* armazenamento bloqueado não pode impedir a saída */
  }
  janela.location.replace("/");
  return true;
}
