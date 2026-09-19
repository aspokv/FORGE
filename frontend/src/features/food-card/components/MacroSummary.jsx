import {CORES, RESUMO, TIPO} from "../lib/layout";
import FoodIcon from "./FoodIcon";

/**
 * O resumo da refeição, fixo na base da peça.
 *
 * Mostra o total da refeição COMPLETA, e não a soma dos alimentos destacados. Destacar
 * quatro de sete não pode fazer o rodapé mentir sobre o que a pessoa comeu — o backend
 * já calcula assim, e este componente só desenha o que recebe.
 */
const COLUNAS = [
  {chave: "protein", rotulo: "PROTEÍNA", unidade: "g"},
  {chave: "carbs", rotulo: "CARBOIDRATOS", unidade: "g"},
  {chave: "fat", rotulo: "GORDURA", unidade: "g"},
  {chave: "calories", rotulo: "ENERGIA", unidade: "kcal"},
];

export default function MacroSummary({summary}) {
  const total = summary || {};
  return (
    <div className="fc-resumo" data-testid="fc-resumo" style={{
      left: RESUMO.margem, right: RESUMO.margem,
      bottom: RESUMO.distanciaDaBase, height: RESUMO.alturaDoBloco,
      borderRadius: RESUMO.raio,
    }}>
      {COLUNAS.map((coluna, i) => (
        <div className="fc-resumo-item" key={coluna.chave}
             style={i ? {borderLeft: `1px solid ${CORES.divisor}`} : undefined}>
          <FoodIcon chave={coluna.chave} familia="macro" tamanho={RESUMO.icone} traco={1.7} />
          <div>
            <span style={{
              fontSize: TIPO.rotuloDoResumo.tamanho,
              fontWeight: TIPO.rotuloDoResumo.peso,
              letterSpacing: TIPO.rotuloDoResumo.espaco,
            }}>{coluna.rotulo}</span>
            <b style={{
              fontSize: TIPO.valorDoResumo.tamanho,
              fontWeight: TIPO.valorDoResumo.peso,
            }}>{Math.round(Number(total[coluna.chave] || 0))} {coluna.unidade}</b>
          </div>
        </div>
      ))}
    </div>
  );
}
