import {useCallback, useEffect, useState} from "react";
import axios from "axios";
import {mensagemDeErro} from "../../mensagemDeErro";
import FoodSelector from "./FoodSelector";
import FoodCardEditor from "./FoodCardEditor";
import "../food-card.css";

/**
 * A porta de entrada do Forge Food Card.
 *
 * Três estados, nesta ordem:
 *
 *   ESCOLHER   a refeição tem mais de quatro alimentos e o atleta decide quais destacar
 *   EDITOR     o card existe e é editável
 *   VAZIO      não há refeição pesada para transformar em peça
 *
 * Quando a refeição tem até quatro alimentos, a escolha é pulada: perguntar "quais dos
 * três você quer" quando a resposta só pode ser "os três" é uma tela a mais sem decisão
 * nenhuma dentro.
 */
export default function ForgeFoodCard({API, dia, entryId, mealIndex, onFechar,
                                       axiosCliente = axios}) {
  const [alimentos, setAlimentos] = useState(null);
  const [maximo, setMaximo] = useState(4);
  const [cardId, setCardId] = useState(null);
  const [estado, setEstado] = useState("carregando");
  const [erro, setErro] = useState("");

  const criar = useCallback(async escolhidos => {
    setErro("");
    try {
      const r = await axiosCliente.post(`${API}/food-card`, {
        date: dia,
        ...(entryId ? {entry_id: entryId} : {}),
        ...(mealIndex !== undefined && mealIndex !== null ? {meal_index: mealIndex} : {}),
        ...(escolhidos?.length ? {food_ids: escolhidos} : {}),
      });
      setCardId(r.data.id);
      setEstado("editor");
    } catch (e) {
      setErro(mensagemDeErro(e, "Não foi possível criar o Food Card."));
      setEstado("erro");
    }
  }, [API, axiosCliente, dia, entryId, mealIndex]);

  useEffect(() => {
    let vivo = true;
    (async () => {
      try {
        const parametros = new URLSearchParams({date: dia});
        if (entryId) parametros.set("entry_id", entryId);
        if (mealIndex !== undefined && mealIndex !== null) {
          parametros.set("meal_index", String(mealIndex));
        }
        const r = await axiosCliente.get(`${API}/food-card/meal?${parametros}`);
        if (!vivo) return;
        setAlimentos(r.data.foods || []);
        setMaximo(r.data.maxItems || 4);
        // Até o máximo, não há escolha a fazer: cria direto.
        if ((r.data.foods || []).length <= (r.data.maxItems || 4)) {
          await criar(null);
        } else {
          setEstado("escolher");
        }
      } catch (e) {
        if (!vivo) return;
        setEstado(e?.response?.status === 404 ? "vazio" : "erro");
        setErro(mensagemDeErro(e, "Não foi possível ler essa refeição."));
      }
    })();
    return () => { vivo = false; };
  }, [API, axiosCliente, dia, entryId, mealIndex, criar]);

  if (estado === "carregando") {
    return <div className="fc-entrada" role="status" data-testid="fc-carregando">
      Preparando seu Food Card…
    </div>;
  }

  if (estado === "vazio") {
    return (
      <div className="fc-entrada fc-vazio" data-testid="fc-vazio">
        <h3>Registre uma refeição primeiro</h3>
        <p>
          O Food Card usa os alimentos e os macros que você pesou. Sem refeição
          registrada não há o que mostrar — e inventar número numa peça que você publica
          não é uma opção.
        </p>
        <button type="button" className="fc-acao-principal" onClick={onFechar}>
          Registrar refeição
        </button>
      </div>
    );
  }

  if (estado === "erro") {
    return (
      <div className="fc-entrada" data-testid="fc-entrada-erro">
        <p role="alert">{erro}</p>
        <button type="button" className="fc-acao-secundaria" onClick={onFechar}>Voltar</button>
      </div>
    );
  }

  if (estado === "escolher") {
    return <div className="fc-entrada">
      <FoodSelector alimentos={alimentos} maximo={maximo}
                    onConfirmar={criar} onCancelar={onFechar} />
    </div>;
  }

  return <FoodCardEditor API={API} cardId={cardId} onVoltar={onFechar}
                         axiosCliente={axiosCliente} />;
}
