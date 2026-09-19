import {CONECTOR, CORES, LARGURA, ALTURA, caixaDoCartao, paraPixel, saidaDoConector} from "../lib/layout";

/**
 * A linha que liga o card ao ponto da foto onde o alimento está.
 *
 * O atleta NÃO desenha a linha. Ela é sempre a reta entre a borda do card e o âncora, e
 * se refaz sozinha quando qualquer um dos dois se move — é o que a especificação pede, e
 * é o que impede uma linha "esquecida" apontando para o lugar errado depois de um arrasto.
 *
 * A saída é calculada pela borda MAIS PRÓXIMA do âncora, e não por um canto fixo: saindo
 * sempre do mesmo canto, a linha atravessaria o próprio card quando o âncora ficasse do
 * outro lado.
 *
 * Um SVG só cobre os quatro conectores. Um por card empilharia quatro camadas de
 * `position:absolute` do tamanho da peça inteira, e cada uma capturaria ponteiro.
 */
export default function FoodConnector({itens, selecionado = null, onPointerDownAncora}) {
  return (
    <svg className="fc-conectores" viewBox={`0 0 ${LARGURA} ${ALTURA}`}
         width={LARGURA} height={ALTURA} fill="none" aria-hidden="true">
      {itens.map((item, i) => {
        const ancora = paraPixel(item.anchorX, item.anchorY);
        const saida = saidaDoConector(caixaDoCartao(item), ancora);
        const ativo = selecionado === i;
        return (
          <g key={item.foodId || i} data-testid={`fc-conector-${i}`}>
            <line x1={saida.x} y1={saida.y} x2={ancora.x} y2={ancora.y}
                  stroke={CORES.linha} strokeWidth={CONECTOR.traco} strokeLinecap="round"
                  opacity={ativo ? 1 : 0.92} />
            {/* O halo é só alvo de toque: 32 px lógicos de diâmetro dão um alvo
                confortável no dedo sem engordar o ponto que aparece na peça. */}
            {onPointerDownAncora ? (
              <circle cx={ancora.x} cy={ancora.y} r={CONECTOR.raioDoHalo * 2}
                      fill="transparent" style={{pointerEvents: "all", cursor: "grab"}}
                      data-testid={`fc-ancora-${i}`}
                      onPointerDown={e => onPointerDownAncora(e, i)} />
            ) : null}
            <circle cx={ancora.x} cy={ancora.y} r={CONECTOR.raioDoPonto}
                    fill={CORES.linha} stroke="rgba(0,0,0,0.35)" strokeWidth="1.5" />
          </g>
        );
      })}
    </svg>
  );
}
