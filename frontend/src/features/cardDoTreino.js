/**
 * O card do treino da tela inicial (arte v1): foto de fundo inteira, texto por cima à
 * esquerda, e à direita a marca, o mapa dos músculos da sessão e uma frase curta.
 *
 * A arte v1 foi feita sem nenhuma letra: título, séries, duração e botão são HTML por
 * cima dela. Isso mantém o texto acessível, traduzível e com os números de verdade da
 * sessão — uma arte com texto embutido mentiria no dia em que o treino mudasse.
 */
import {buildSessionMuscles, getAnatomyAssetKey, getSessionZone} from "./MuscleSessionMap";

/** "Peito dominante, costas e braços" -> ["Peito dominante,", " costas e braços"].
 *  A primeira parte sai clara e a segunda em laranja, como na referência. Sem vírgula, a
 *  última palavra leva a cor. O texto inteiro continua igual — só muda a cor. */
export function tituloEmDuasCores(titulo) {
  const texto = String(titulo || "");
  const virgula = texto.indexOf(",");
  if (virgula > 0 && virgula < texto.length - 1) return [texto.slice(0, virgula + 1), texto.slice(virgula + 1)];
  const espaco = texto.trimEnd().lastIndexOf(" ");
  if (espaco > 0) return [texto.slice(0, espaco), texto.slice(espaco)];
  return [texto, ""];
}

// Uma frase por tipo de arte. Curta: ela divide a coluna da direita com o mapa.
const FRASES = {
  push: "Força de empurrar: peito, ombros e tríceps",
  pull: "Costas largas e puxada forte",
  "legs-quads": "Quadríceps fortes e base sólida",
  "legs-posterior": "Glúteos mais fortes, com estabilidade e definição",
  upper: "Construção de força e volume real",
  fullbody: "O corpo inteiro na mesma sessão",
  chest: "Peitoral cheio e forte",
  back: "Espessura e largura de costas",
  shoulders: "Ombros largos e estáveis",
  arms: "Braços com volume e definição",
  default: "Constância que vira resultado",
};

export function fraseDoCard(categoria) {
  return FRASES[categoria] || FRASES.default;
}

// Mapas de costas: o que se trabalha nelas aparece melhor visto por trás.
const DE_COSTAS = new Set(["pull", "back-width", "back-thickness", "glutes", "hamstrings", "legs-posterior", "calves"]);

/** Quais vistas do mapa mostrar: sessão de membros inferiores ou de corpo inteiro mostra
 *  frente e costas (como a referência de glúteos); o resto mostra o lado que trabalha. */
export function mapaDoCard(itens = [], exercicios = [], foco = [], nomeDaSessao = "") {
  const carga = buildSessionMuscles(itens, exercicios, foco);
  const zona = getSessionZone(carga);
  const chave = getAnatomyAssetKey(carga, nomeDaSessao);
  const lados = zona === "lower" || zona === "full" || chave === "lower" || chave === "full-body"
    ? ["front", "back"] : DE_COSTAS.has(chave) ? ["back"] : ["front"];
  return {chave, lados};
}
