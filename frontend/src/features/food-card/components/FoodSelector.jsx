import {useState} from "react";
import {Check} from "lucide-react";
import FoodIcon from "./FoodIcon";
import {quantidadeDe} from "../lib/conteudo";

/**
 * A escolha de quais alimentos viram card.
 *
 * Aparece quando a refeição tem mais de quatro. O limite não é estético: cinco cards numa
 * peça de 1080 x 1920 ou se sobrepõem ou ficam pequenos demais para ler no Story.
 *
 * O resumo inferior continua somando a refeição COMPLETA. Destacar quatro de sete é uma
 * decisão de composição, não de contabilidade, e o rodapé não pode mentir sobre o que a
 * pessoa comeu.
 */
export default function FoodSelector({alimentos = [], maximo = 4, onConfirmar, onCancelar}) {
  const [escolhidos, setEscolhidos] = useState(
    () => alimentos.slice(0, maximo).map(a => a.foodId));

  const alternar = foodId => {
    setEscolhidos(atual => {
      if (atual.includes(foodId)) return atual.filter(x => x !== foodId);
      if (atual.length >= maximo) return atual;
      return [...atual, foodId];
    });
  };

  const cheio = escolhidos.length >= maximo;

  return (
    <section className="fc-selector" data-testid="fc-selector">
      <header>
        <h3>Escolha até {maximo} alimentos para destacar</h3>
        <p>O resumo no rodapé continua somando a refeição inteira.</p>
      </header>

      <ul className="fc-selector-lista">
        {alimentos.map(alimento => {
          const marcado = escolhidos.includes(alimento.foodId);
          const bloqueado = !marcado && cheio;
          return (
            <li key={alimento.foodId}>
              <button type="button" role="checkbox" aria-checked={marcado}
                      disabled={bloqueado}
                      data-testid={`fc-selector-${alimento.foodId}`}
                      className={marcado ? "marcado" : ""}
                      onClick={() => alternar(alimento.foodId)}>
                <span className="fc-selector-caixa" aria-hidden="true">
                  {marcado ? <Check size={14} /> : null}
                </span>
                <FoodIcon chave={alimento.iconKey} tamanho={22} traco={1.5} />
                <span className="fc-selector-nome">
                  <b>{alimento.name}</b>
                  <small>{quantidadeDe(alimento)}</small>
                </span>
              </button>
            </li>
          );
        })}
      </ul>

      <div className="fc-selector-acoes">
        <button type="button" className="fc-acao-principal" disabled={!escolhidos.length}
                data-testid="fc-selector-confirmar"
                onClick={() => onConfirmar(escolhidos)}>
          Criar Food Card
        </button>
        {onCancelar ? (
          <button type="button" className="fc-acao-secundaria" onClick={onCancelar}>
            Cancelar
          </button>
        ) : null}
      </div>
    </section>
  );
}
