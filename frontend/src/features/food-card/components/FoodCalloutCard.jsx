import {CARTAO, TIPO, caixaDoCartao} from "../lib/layout";
import {ROTULO_DO_MACRO, descricaoDe, quantidadeDe, valorDoMacro} from "../lib/conteudo";
import FoodIcon from "./FoodIcon";

/**
 * O card de um alimento, em cima da foto.
 *
 * Desenhado em pixels LÓGICOS de 1080 x 1920 — o canvas inteiro é encolhido por
 * `transform: scale()`, então aqui não existe "tamanho para celular". Isso é o que faz a
 * prévia e a exportação terem a mesma composição: elas leem as mesmas constantes.
 *
 * O card tem duas partes separadas por uma linha fina, como na referência:
 *
 *   NOME DO ALIMENTO / QUANTIDADE / descrição curta
 *   ─────────────────────────────
 *   ÍCONE DO MACRO / MACRO PRINCIPAL / VALOR
 *
 * Quando não há descrição segura para o alimento, o bloco some inteiro. Não existe texto
 * de preenchimento: a alternativa seria inventar uma alegação nutricional numa peça que
 * o atleta publica com o nome do FORGE em cima.
 */
export default function FoodCalloutCard({
  item, selecionado = false, arrastando = false, onPointerDown, indice = 0,
}) {
  const caixa = caixaDoCartao(item);
  const descricao = descricaoDe(item);
  const rotulo = ROTULO_DO_MACRO[item.primaryMacro] || ROTULO_DO_MACRO.protein;

  const classe = [
    "fc-callout",
    selecionado ? "fc-callout-selecionado" : "",
    arrastando ? "fc-callout-arrastando" : "",
  ].filter(Boolean).join(" ");

  return (
    <div
      className={classe}
      data-testid={`fc-card-${indice}`}
      style={{
        left: `${caixa.x}px`, top: `${caixa.y}px`,
        width: `${CARTAO.largura}px`, borderRadius: `${CARTAO.raio}px`,
        padding: `${CARTAO.padding}px`,
      }}
      onPointerDown={onPointerDown}
      role={onPointerDown ? "button" : undefined}
      tabIndex={onPointerDown ? 0 : undefined}
      aria-label={onPointerDown
        ? `${item.name}, ${quantidadeDe(item)}. Arraste para reposicionar.`
        : undefined}
    >
      <div className="fc-callout-topo">
        <span className="fc-callout-icone"
              style={{width: CARTAO.icone.tamanho, height: CARTAO.icone.tamanho}}>
          <FoodIcon chave={item.iconKey} tamanho={CARTAO.icone.tamanho * 0.56} />
        </span>
        <div className="fc-callout-texto">
          <b className="fc-callout-nome" style={{
            fontSize: TIPO.nomeDoAlimento.tamanho,
            fontWeight: TIPO.nomeDoAlimento.peso,
            letterSpacing: TIPO.nomeDoAlimento.espaco,
          }}>{item.name.toUpperCase()}</b>
          <span className="fc-callout-quantidade" style={{
            fontSize: TIPO.quantidade.tamanho,
            fontWeight: TIPO.quantidade.peso,
          }}>{quantidadeDe(item)}</span>
          {descricao ? (
            <span className="fc-callout-descricao" style={{
              fontSize: TIPO.descricao.tamanho,
              lineHeight: `${TIPO.descricao.entrelinha}px`,
            }}>{descricao}</span>
          ) : null}
        </div>
      </div>

      <div className="fc-callout-divisor" style={{marginTop: CARTAO.divisorY}} />

      <div className="fc-callout-macro" style={{height: CARTAO.alturaDoBlocoDoMacro}}>
        <FoodIcon chave={item.primaryMacro} familia="macro" tamanho={40} />
        <div>
          <span className="fc-callout-macro-rotulo" style={{
            fontSize: TIPO.rotuloDoMacro.tamanho,
            fontWeight: TIPO.rotuloDoMacro.peso,
            letterSpacing: TIPO.rotuloDoMacro.espaco,
          }}>{rotulo}</span>
          <b className="fc-callout-macro-valor" style={{
            fontSize: TIPO.valorDoMacro.tamanho,
            fontWeight: TIPO.valorDoMacro.peso,
          }}>{valorDoMacro(item)} g</b>
          <span className="fc-callout-porcao" style={{fontSize: TIPO.porcao.tamanho}}>
            por porção
          </span>
        </div>
      </div>
    </div>
  );
}
