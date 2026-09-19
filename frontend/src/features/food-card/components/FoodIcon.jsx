import {QUADRO, caminhosDoAlimento, caminhosDoMacro} from "../lib/icones";

/**
 * Um ícone da peça, em traço.
 *
 * Existe em duas famílias — alimento e macro — e ambas desenham do mesmo jeito: caminhos
 * com `stroke`, nunca `fill`, para quem chama definir espessura e cor. É o que permite o
 * mesmo ícone servir ao círculo do card e ao resumo inferior sem uma segunda versão.
 *
 * `aria-hidden` é deliberado: o ícone repete uma informação que já está escrita ao lado
 * em texto. Anunciá-lo de novo faria o leitor de tela dizer "imagem, carne, carne".
 */
export default function FoodIcon({
  chave, familia = "alimento", tamanho = 24, traco = 1.6, cor = "currentColor",
  className = "",
}) {
  const caminhos = familia === "macro" ? caminhosDoMacro(chave) : caminhosDoAlimento(chave);
  return (
    <svg className={`food-icon ${className}`} width={tamanho} height={tamanho}
         viewBox={`0 0 ${QUADRO} ${QUADRO}`} fill="none" aria-hidden="true" focusable="false">
      {caminhos.map((d, i) => (
        <path key={i} d={d} stroke={cor} strokeWidth={traco}
              strokeLinecap="round" strokeLinejoin="round" />
      ))}
    </svg>
  );
}
