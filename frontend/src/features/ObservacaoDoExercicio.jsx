import {useCallback, useEffect, useRef, useState} from "react";
import axios from "axios";
import {PencilLine} from "lucide-react";
import "./observacao-do-exercicio.css";

/**
 * A observação que o atleta escreve embaixo do exercício, durante o treino.
 *
 * "A máquina de tríceps estava ocupada, usei a polia alta." Sem um lugar para isso, na
 * semana seguinte a pessoa olha 40 kg no histórico e não lembra que foi em outro aparelho,
 * e o número vira uma comparação errada que ela mesma fez.
 *
 * Por que a anterior aparece
 * --------------------------
 * A primeira observação qualquer um escreve. A segunda só aparece se a primeira voltar.
 * Por isso a nota da última vez fica visível acima do campo: a anotação deixa de ser um
 * diário e vira instrução para hoje. Diário a pessoa abandona na segunda semana.
 *
 * Salva enquanto se digita, com atraso, e de novo ao sair do campo. As duas coisas batem
 * na mesma rota, que é idempotente por (perfil, exercício, dia): repetir não cria linha.
 */

const ATRASO_MS = 900;

export default function ObservacaoDoExercicio({
  API, exerciseId, sessionDay = null, dia, inicial = "", anterior = null,
  axiosCliente = axios,
}) {
  const [texto, setTexto] = useState(inicial);
  const [aberto, setAberto] = useState(Boolean(inicial));
  const [estado, setEstado] = useState("parado");    // parado | salvando | salvo | erro
  const relogio = useRef(null);
  const ultimoSalvo = useRef(inicial);

  useEffect(() => {
    setTexto(inicial);
    ultimoSalvo.current = inicial;
    if (inicial) setAberto(true);
  }, [inicial, exerciseId]);

  const salvar = useCallback(async valor => {
    if (valor === ultimoSalvo.current) return;
    setEstado("salvando");
    try {
      await axiosCliente.post(`${API}/exercise-note`, {
        exercise_id: exerciseId, date: dia, session_day: sessionDay, texto: valor,
      });
      ultimoSalvo.current = valor;
      setEstado("salvo");
    } catch {
      // Sem texto de erro grande no meio de uma série: a observação é acessória e não
      // pode roubar a atenção de quem está treinando. O estado fica marcado e a próxima
      // digitação tenta de novo.
      setEstado("erro");
    }
  }, [API, axiosCliente, dia, exerciseId, sessionDay]);

  useEffect(() => () => clearTimeout(relogio.current), []);

  const digitar = valor => {
    setTexto(valor);
    setEstado("parado");
    clearTimeout(relogio.current);
    relogio.current = setTimeout(() => salvar(valor), ATRASO_MS);
  };

  const sair = () => {
    clearTimeout(relogio.current);
    salvar(texto);
  };

  if (!aberto) return (
    <button type="button" className="obs-abrir" data-testid={`obs-abrir-${exerciseId}`}
            onClick={() => setAberto(true)}>
      <PencilLine size={13} /> Observação
    </button>
  );

  return (
    <div className="obs-exercicio" data-testid={`obs-${exerciseId}`}>
      {anterior?.texto ? (
        <p className="obs-anterior" data-testid={`obs-anterior-${exerciseId}`}>
          <b>Da última vez:</b> {anterior.texto}
        </p>
      ) : null}
      <label>
        <span className="obs-rotulo">
          Observação
          {estado === "salvo" ? <i data-testid={`obs-estado-${exerciseId}`}>salvo</i> : null}
          {estado === "erro" ? <i className="falhou" data-testid={`obs-estado-${exerciseId}`}>não salvou</i> : null}
        </span>
        <textarea
          value={texto}
          rows={2}
          maxLength={400}
          placeholder="A máquina estava ocupada, usei a polia alta"
          data-testid={`obs-campo-${exerciseId}`}
          onChange={e => digitar(e.target.value)}
          onBlur={sair}
        />
      </label>
    </div>
  );
}
