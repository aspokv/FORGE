/**
 * Busca de alimento que aguenta dedo em teclado de celular.
 *
 * O atleta digitou "abulmina" procurando albumina e a tela disse "alimento nao encontrado".
 * O catalogo tinha o alimento; quem falhou foi a comparacao, que era substring exata. Numa
 * tela onde a pessoa digita com uma mao, suando, entre uma refeicao e outra, exigir grafia
 * perfeita e transformar um erro de digitacao em "o app nao tem o que eu como".
 *
 * A regra central: o afrouxamento so entra quando a busca exata nao achou NADA. Enquanto
 * houver resultado exato, ele manda sozinho — senao "arroz" comecaria a trazer "arroz" e
 * "argos" lado a lado, e a lista boa viraria lista confusa.
 */

/** Sem acento, sem caixa, sem espaco sobrando: "Maçã" e "maca" viram a mesma coisa. */
export function normalizar(texto) {
  return String(texto || "")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .trim();
}

/** O texto pesquisavel de um alimento: o nome mais todos os apelidos. */
function textoDoAlimento(alimento) {
  return normalizar([alimento?.name, ...(alimento?.aliases || [])].join(" "));
}

/**
 * Distancia de Damerau-Levenshtein, com corte.
 *
 * Damerau e nao Levenshtein simples por causa da transposicao: trocar duas letras de lugar
 * e o erro mais comum de quem digita rapido, e no Levenshtein puro ele custa 2 — o dobro do
 * que deveria. "albumina" -> "abulmina" sao duas transposicoes; no Levenshtein puro daria 3
 * substituicoes e escaparia de qualquer limite razoavel.
 *
 * O corte (`maximo`) existe porque isto roda a cada tecla contra o catalogo inteiro: sem
 * ele, comparar palavras muito diferentes gastaria a matriz toda para nada.
 */
export function distancia(a, b, maximo = 2) {
  if (a === b) return 0;
  if (Math.abs(a.length - b.length) > maximo) return maximo + 1;
  const linhas = a.length + 1;
  const colunas = b.length + 1;
  let anterior2 = null;
  let anterior = Array.from({ length: colunas }, (_, j) => j);
  for (let i = 1; i < linhas; i += 1) {
    const atual = new Array(colunas);
    atual[0] = i;
    let menorNaLinha = atual[0];
    for (let j = 1; j < colunas; j += 1) {
      const custo = a[i - 1] === b[j - 1] ? 0 : 1;
      let valor = Math.min(atual[j - 1] + 1, anterior[j] + 1, anterior[j - 1] + custo);
      // A transposicao: as duas ultimas letras trocadas contam como UM erro.
      if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) {
        valor = Math.min(valor, anterior2[j - 2] + 1);
      }
      atual[j] = valor;
      if (valor < menorNaLinha) menorNaLinha = valor;
    }
    // Nenhuma celula desta linha ficou dentro do limite: o resto so piora.
    if (menorNaLinha > maximo) return maximo + 1;
    anterior2 = anterior;
    anterior = atual;
  }
  return anterior[colunas - 1];
}

/**
 * Quanto erro se tolera num termo, pelo tamanho dele.
 *
 * Palavra curta nao ganha tolerancia: com tres letras, distancia 1 liga "uva" a "ova", a
 * "iva" e a meio catalogo. O ganho aparece nas palavras longas, que sao justamente onde a
 * pessoa erra — "albumina", "maltodextrina", "hipercalorico".
 */
export function tolerancia(termo) {
  if (termo.length >= 7) return 2;
  if (termo.length >= 5) return 1;
  return 0;
}

/** Casamento exato: todo termo da busca aparece no texto do alimento. */
export function casaExato(alimento, consulta) {
  const termos = normalizar(consulta).split(/\s+/).filter(Boolean);
  if (!termos.length) return true;
  const texto = textoDoAlimento(alimento);
  return termos.every((termo) => texto.includes(termo));
}

/**
 * Casamento aproximado: cada termo precisa estar perto de ALGUMA palavra do alimento.
 *
 * Compara palavra a palavra, e nao com o texto inteiro, porque distancia contra uma frase
 * longa e sempre enorme e nunca casaria nada.
 */
export function casaAproximado(alimento, consulta) {
  const termos = normalizar(consulta).split(/\s+/).filter(Boolean);
  if (!termos.length) return true;
  const palavras = textoDoAlimento(alimento).split(/[\s,()/—-]+/).filter(Boolean);
  return termos.every((termo) => {
    if (palavras.some((palavra) => palavra.includes(termo))) return true;
    const limite = tolerancia(termo);
    if (!limite) return false;
    return palavras.some((palavra) => {
      // Palavra muito maior que o termo nao e erro de digitacao, e outra palavra.
      if (Math.abs(palavra.length - termo.length) > limite) return false;
      return distancia(termo, palavra, limite) <= limite;
    });
  });
}

/**
 * Quantas palavras o nome tem alem do que foi digitado.
 *
 * Ignora explicacao entre parenteses e sufixo de marca depois de travessao, porque medir o
 * nome cru premia a marca: "Albumina — Naturovos" e mais curto que "Albumina (clara de ovo
 * desidratada)", e quem digita "albumina" quer a albumina, nao a marca que alguem cadastrou.
 */
export function palavrasAMais(termo, nome) {
  const limpo = String(nome || "").replace(/\([^)]*\)/g, " ").split(/\s[—–-]\s/)[0];
  const doTermo = new Set(normalizar(termo).split(/\s+/).filter(Boolean));
  return normalizar(limpo).split(/\s+/).filter((p) => p && !doTermo.has(p)).length;
}

/**
 * A ordem entre alimentos que casaram igual. Menor vem primeiro.
 *
 * Por que isto existe: a lista saia na ORDEM DO CATALOGO, que nao tem relacao com o que a
 * pessoa digitou. "arroz" devolvia "Biscoito de arroz", "Marmita de frango, arroz e
 * brocolis" e "Proteina vegetal" — sem arroz nos tres primeiros. "leite" nao trazia leite,
 * "frango" trazia coxa e strogonoff antes do peito, "tomate" trazia molho antes do tomate.
 *
 * A tela mostra os resultados numa coluna de celular, e o primeiro e o que a pessoa toca.
 * Achar o alimento nao serve para nada se ele estiver em decimo.
 *
 * A ordem dos critérios espelha `_precisao` + o desempate de `buscar_para_montagem` no
 * backend, para a mesma busca nao dar respostas diferentes em duas telas do mesmo app.
 */
function ordem(alimento, termo) {
  const nome = normalizar(alimento?.name);
  const apelidos = (alimento?.aliases || []).map(normalizar);
  return [
    // 1. O nome cita o termo? Apelido casa menos que nome: "alcatra" deve trazer "Alcatra
    //    grelhada" antes de "Carne bovina grelhada (patinho)", que so a lista como apelido.
    nome.includes(termo) ? 0 : 1,
    // 2. Alimento-base antes de prato pronto e de marca. O motor so dimensiona o primeiro
    //    sozinho, e e por isso que "frango" tem de cair em peito de frango.
    alimento?.dimensionavel ? 0 : 1,
    // 3. Onde o termo aparece: o nome inteiro, o comeco, ou o meio.
    nome === termo ? 0 : nome.startsWith(`${termo} `) ? 1 : 2,
    // 4. Apelido exato e intencao de quem montou o catalogo: "leite" esta cadastrado no
    //    integral, "feijao" no carioca.
    apelidos.includes(termo) ? 0 : 1,
    // 5. O alimento mais simples se descreve com menos palavras.
    palavrasAMais(termo, alimento?.name),
  ];
}

function ordenar(itens, termo) {
  return itens
    .map((alimento) => ({ alimento, chave: ordem(alimento, termo) }))
    .sort((a, b) => {
      for (let i = 0; i < a.chave.length; i += 1) {
        if (a.chave[i] !== b.chave[i]) return a.chave[i] - b.chave[i];
      }
      // Empate completo: alfabeto, para a lista nao mudar de ordem entre renderizacoes.
      return String(a.alimento?.name || "").localeCompare(String(b.alimento?.name || ""), "pt");
    })
    .map((x) => x.alimento);
}

/**
 * O resultado que a tela mostra.
 *
 * Exato primeiro e sozinho. So quando ele vem vazio a rede se abre, e ai os aproximados
 * entram marcados, para a tela poder dizer que aquilo e um palpite e nao um acerto.
 */
export function buscarNoCatalogo(catalogo = [], consulta = "") {
  const lista = catalogo || [];
  const termo = normalizar(consulta);
  // Sem busca, a tela lista o catalogo para a pessoa navegar. Devolver vazio aqui apagaria
  // a lista inicial do editor, que e como alguem que nao sabe o nome exato acha o alimento.
  // Fica na ordem do catalogo de proposito: sem termo nao existe "mais relevante".
  if (!termo) return { itens: lista, aproximado: false };
  const exatos = lista.filter((alimento) => casaExato(alimento, consulta));
  if (exatos.length) return { itens: ordenar(exatos, termo), aproximado: false };
  const proximos = lista.filter((alimento) => casaAproximado(alimento, consulta));
  return { itens: ordenar(proximos, termo), aproximado: proximos.length > 0 };
}
