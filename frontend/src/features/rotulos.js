/**
 * O vocabulario que o produto mostra, separado do vocabulario que ele guarda.
 *
 * Duas coisas vazavam para a tela e as duas custam credibilidade:
 *
 * 1. Uma data literal no cabecalho — `06 JUN 2026` estava escrita no codigo e aparecia em
 *    toda aba, todo dia, para todo mundo. Num produto de acompanhamento, data errada no
 *    topo faz o resto parecer maquete.
 *
 * 2. Constantes de banco como titulo: `FORGE_AUTO`, `ELITE`, `ACTIVE`. Sublinhado e caixa
 *    alta denunciam que ninguem traduziu o sistema para a lingua de quem usa.
 *
 * Rotulo desconhecido volta legivel em vez de vazio: uma chave nova no backend nao deve
 * abrir um buraco na interface.
 */

/** "06 de setembro" — a data real do aparelho, no fuso de quem esta olhando. */
export function dataDoCabecalho(quando = new Date()) {
  const d = quando instanceof Date ? quando : new Date(quando);
  if (Number.isNaN(d.getTime())) return "";
  return new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "long" }).format(d);
}

/** "Domingo, 06 de setembro" — versao longa, para quando a tela tem espaco. */
export function dataPorExtenso(quando = new Date()) {
  const d = quando instanceof Date ? quando : new Date(quando);
  if (Number.isNaN(d.getTime())) return "";
  const cru = new Intl.DateTimeFormat("pt-BR", {
    weekday: "long", day: "2-digit", month: "long",
  }).format(d).replace("-feira", "");
  return cru.charAt(0).toUpperCase() + cru.slice(1);
}

const MODO = {
  FORGE_AUTO: "Programação automática",
  FORGE_ASSISTED: "Programação assistida",
  FORGE_PRO: "Programação manual",
};

const PLANO = {
  ESSENTIAL: "Essencial",
  ESSENCIAL: "Essencial",
  PRO: "Pro",
  ELITE: "Elite",
};

const SITUACAO = {
  ACTIVE: "Ativo",
  PENDING: "Convite pendente",
  PENDING_PAYMENT: "Pagamento pendente",
  EXPIRED: "Plano expirado",
  SUSPENDED: "Conta suspensa",
};

/**
 * Transforma uma constante em texto legivel.
 *
 * Sem correspondencia, devolve a chave com o sublinhado desfeito e so a primeira letra em
 * maiuscula — pior que traduzido, melhor que `FORGE_AUTO` gritando na tela.
 */
function traduzir(tabela, chave) {
  if (!chave) return "";
  const bruto = String(chave).trim();
  if (tabela[bruto.toUpperCase()]) return tabela[bruto.toUpperCase()];
  const limpo = bruto.replace(/_/g, " ").toLowerCase();
  return limpo.charAt(0).toUpperCase() + limpo.slice(1);
}

export const rotuloDoModo = (v) => traduzir(MODO, v);
export const rotuloDoPlano = (v) => traduzir(PLANO, v);
export const rotuloDaSituacao = (v) => traduzir(SITUACAO, v);
