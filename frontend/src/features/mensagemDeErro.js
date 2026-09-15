/**
 * O texto legível de um erro de API, sempre como STRING.
 *
 * Por que isto existe, e por que importa mais do que parece: o backend responde 402 com o
 * detalhe sendo um OBJETO, e não texto —
 *
 *   {message, capability, current_plan, upgrade}
 *
 * Todo lugar que fazia `setErro(e?.response?.data?.detail || "...")` guardava esse objeto no
 * estado e depois tentava renderizar `{erro}` dentro de um parágrafo. React não renderiza
 * objeto como filho: ele lança, a árvore inteira cai e a TELA FICA PRETA.
 *
 * Foi exatamente isso que o atleta viu ao tentar voltar para o ritmo Agressivo — o único
 * caminho da Nutrição que devolve 402. O erro que deveria dizer "seu plano não inclui este
 * recurso" derrubava o aplicativo em vez de explicar.
 *
 * A regra daqui em diante: nada que veio da rede vai para a tela sem passar por aqui.
 */
export function mensagemDeErro(erro, reserva = "Não foi possível completar a ação agora.") {
  const detalhe = erro?.response?.data?.detail;

  if (typeof detalhe === "string" && detalhe.trim()) return detalhe;

  // 402 e outros erros ricos: o texto para a pessoa mora em `message`.
  if (detalhe && typeof detalhe === "object" && !Array.isArray(detalhe)) {
    if (typeof detalhe.message === "string" && detalhe.message.trim()) return detalhe.message;
  }

  // Erro de validação do FastAPI: uma lista de problemas por campo. Mostrar o primeiro é
  // mais útil que "erro de validação", e muito mais útil que despejar a lista inteira.
  if (Array.isArray(detalhe) && detalhe.length) {
    const primeiro = detalhe[0];
    if (typeof primeiro === "string") return primeiro;
    if (typeof primeiro?.msg === "string") return primeiro.msg;
  }

  const solto = erro?.response?.data?.message;
  if (typeof solto === "string" && solto.trim()) return solto;

  return reserva;
}

/**
 * O erro é falta de PLANO, e não falta de permissão.
 *
 * O backend usa 402 de propósito para isso: a interface deve levar para a página de planos
 * em vez de dizer "acesso negado". Quem trata o erro pode decidir o que fazer com isso.
 */
export function ehFaltaDePlano(erro) {
  if (erro?.response?.status === 402) return true;
  return Boolean(erro?.response?.data?.detail?.upgrade);
}
