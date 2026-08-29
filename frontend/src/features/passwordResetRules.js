/**
 * Regras da recuperacao de senha, separadas da tela.
 *
 * O servidor revalida tudo: o que esta aqui existe para a pessoa corrigir antes de
 * enviar. A politica de senha e a mesma dos dois lados de proposito — divergir
 * significaria a tela aprovar o que o servidor recusa, ou o contrario.
 */

export const PASSO_PEDIR = "pedir";
export const PASSO_ENVIADO = "enviado";
export const PASSO_NOVA_SENHA = "nova";
export const PASSO_PRONTO = "pronto";
export const PASSO_LINK_INVALIDO = "invalido";

export const SENHA_MINIMA = 8;

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export function emailParece(valor) {
  return EMAIL.test(String(valor || "").trim());
}

/**
 * Mesma politica do backend (auth.senha_fraca). Devolve o que falta, nao um "fraca"
 * mudo: quem esta trocando a senha precisa saber o que mudar.
 */
export function problemaDaSenha(senha, email = "") {
  const s = String(senha || "");
  if (s.length < SENHA_MINIMA) {
    return `A senha precisa de pelo menos ${SENHA_MINIMA} caracteres.`;
  }
  // Antes das checagens de letra e numero: uma senha de um caractere so repetido sempre
  // falharia numa delas primeiro, e este aviso nunca apareceria.
  if (new Set(s).size === 1) return "A senha precisa de caracteres variados.";
  if (!/[a-zA-Z]/.test(s)) return "A senha precisa de pelo menos uma letra.";
  if (!/\d/.test(s)) return "A senha precisa de pelo menos um número.";
  const local = String(email || "").split("@")[0].toLowerCase();
  if (local.length >= 3 && s.toLowerCase().includes(local)) {
    return "A senha não pode conter seu e-mail.";
  }
  return null;
}

export function senhasConferem(senha, confirmacao) {
  return String(senha || "") === String(confirmacao || "");
}

/**
 * Traduz a falha da API.
 *
 * Usa o `reason` que o backend envia; depender do texto quebraria assim que alguem
 * reescrevesse a frase do outro lado.
 */
export function explicarErro(e) {
  const resposta = e && e.response;
  const status = resposta && resposta.status;
  const detalhe = resposta && resposta.data && resposta.data.detail;
  const motivo = detalhe && typeof detalhe === "object" ? detalhe.reason : null;

  if (motivo === "reset_token_invalid") {
    return "Este link expirou ou já foi usado. Peça um novo.";
  }
  if (motivo === "weak_password" && detalhe.message) return detalhe.message;
  if (motivo === "rate_limited") return "Muitas tentativas. Aguarde alguns minutos.";
  if (status === 410) return "Este link expirou ou já foi usado. Peça um novo.";
  if (status === 429) return "Muitas tentativas. Aguarde alguns minutos.";
  if (typeof detalhe === "object" && detalhe && detalhe.message) return detalhe.message;
  if (typeof detalhe === "string") return detalhe;
  return "Não foi possível concluir agora. Tente novamente.";
}

/** O token vem da rota /recuperar/<token>. */
export function tokenDaRota(caminho) {
  const m = String(caminho || "").match(/^\/recuperar\/([^/?#]+)/);
  return m ? m[1] : null;
}

/** Um link invalido leva para o passo de erro, e nao para o formulario. */
export function passoInicial(caminho) {
  return tokenDaRota(caminho) ? PASSO_NOVA_SENHA : PASSO_PEDIR;
}
