/**
 * Regras do funil publico de aquisicao, separadas da tela.
 *
 * Ficam aqui, e nao dentro do componente, porque sao o tipo de coisa que precisa de
 * teste: validacao, forca de senha e traducao de erro. Um componente React exigiria
 * biblioteca de renderizacao; uma funcao pura nao exige nada.
 *
 * O servidor revalida tudo isto. O que esta aqui existe para a pessoa saber o que
 * corrigir antes de enviar, nunca como a unica barreira.
 */

export const PASSO_PLANO = "plano";
export const PASSO_DADOS = "dados";
export const PASSO_CODIGO = "codigo";
export const PASSO_SENHA = "senha";
export const PASSO_PAGAMENTO = "pagamento";

export const PASSOS = [
  PASSO_PLANO,
  PASSO_DADOS,
  PASSO_CODIGO,
  PASSO_SENHA,
  PASSO_PAGAMENTO,
];

export const ROTULO_DO_PASSO = {
  [PASSO_PLANO]: "Escolha seu plano",
  [PASSO_DADOS]: "Seus dados",
  [PASSO_CODIGO]: "Confirme seu e-mail",
  [PASSO_SENHA]: "Crie sua senha",
  [PASSO_PAGAMENTO]: "Pagamento",
};

export function proximoPasso(atual) {
  const i = PASSOS.indexOf(atual);
  if (i < 0 || i === PASSOS.length - 1) return atual;
  return PASSOS[i + 1];
}

export function passoAnterior(atual) {
  const i = PASSOS.indexOf(atual);
  return i <= 0 ? atual : PASSOS[i - 1];
}

// Deliberadamente permissivo: a validacao que decide e a do servidor, e recusar um
// endereco valido por excesso de zelo custa um cadastro.
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export function emailParece(valor) {
  return EMAIL.test(String(valor || "").trim());
}

export function validarDados({ name, email, acceptTerms } = {}) {
  const erros = {};
  const nome = String(name || "").trim();
  if (nome.length < 2) erros.name = "Digite seu nome.";
  if (!emailParece(email)) erros.email = "Digite um e-mail válido.";
  if (!acceptTerms) {
    erros.acceptTerms = "É necessário aceitar os Termos e a Política de Privacidade.";
  }
  return { ok: Object.keys(erros).length === 0, erros };
}

export function validarCodigo(code) {
  return /^\d{6}$/.test(String(code || "").trim());
}

/**
 * Forca da senha. Devolve o que falta em vez de um "senha fraca" mudo — quem esta
 * cadastrando precisa saber o que mudar.
 */
export function avaliarSenha(senha, { email } = {}) {
  const s = String(senha || "");
  const problemas = [];
  if (s.length < 8) problemas.push("pelo menos 8 caracteres");
  if (!/[a-zA-Z]/.test(s)) problemas.push("pelo menos uma letra");
  if (!/\d/.test(s)) problemas.push("pelo menos um número");
  if (s && /^(.)\1*$/.test(s)) problemas.push("caracteres variados");

  const local = String(email || "").split("@")[0].toLowerCase();
  if (local.length >= 3 && s.toLowerCase().includes(local)) {
    problemas.push("algo diferente do seu e-mail");
  }

  let nivel = "fraca";
  if (problemas.length === 0) nivel = s.length >= 12 ? "forte" : "boa";

  return { ok: problemas.length === 0, nivel, problemas };
}

/**
 * Traduz a falha da API para uma frase util.
 *
 * O motivo vem do campo `reason`, que o backend manda de proposito: depender do texto
 * da mensagem quebraria assim que alguem reescrevesse a frase do outro lado.
 */
export function explicarErro(e) {
  const resposta = e && e.response;
  const status = resposta && resposta.status;
  const detalhe = resposta && resposta.data && resposta.data.detail;
  const motivo = detalhe && typeof detalhe === "object" ? detalhe.reason : null;

  if (motivo === "public_signup_disabled") {
    return "O cadastro ainda não está aberto. Tente novamente em breve.";
  }
  if (motivo === "too_many_attempts") {
    return "Muitas tentativas. Peça um novo código.";
  }
  if (motivo === "too_many_resends") {
    return "Você pediu o código muitas vezes. Tente novamente mais tarde.";
  }
  if (motivo === "expired") {
    return "Seu cadastro expirou. Comece novamente.";
  }
  if (motivo === "misconfigured" || motivo === "plan_not_configured") {
    return "A assinatura está indisponível no momento. Tente novamente em instantes.";
  }
  if (motivo === "provider_error") {
    return "Não foi possível abrir o pagamento agora. Tente novamente.";
  }
  if (motivo === "already_subscribed") {
    return "Você já tem uma assinatura ativa.";
  }
  if (status === 400 && typeof detalhe === "string") return detalhe;
  if (status === 409) return "Este cadastro já foi concluído. Faça login.";
  if (status === 410) return "Seu cadastro expirou. Comece novamente.";
  if (status === 429) return "Muitas tentativas. Aguarde um momento.";
  if (typeof detalhe === "object" && detalhe && detalhe.message) return detalhe.message;
  if (typeof detalhe === "string") return detalhe;
  return "Não foi possível continuar agora. Tente novamente.";
}

/**
 * O que a tela deve mostrar para quem voltou e ainda nao pagou (item 9 do escopo):
 * o plano escolhido em destaque, os outros continuam disponiveis para troca.
 */
export function montarRetomada(planos, escolhido) {
  const lista = Array.isArray(planos) ? planos : [];
  return {
    escolhido: lista.find((p) => p.code === escolhido) || null,
    alternativas: lista.filter((p) => p.code !== escolhido),
  };
}
