import {useState} from "react";
import axios from "axios";
import ForgeDialog from "./ForgeDialog";
import {mensagemDeErro} from "./mensagemDeErro";

/**
 * Confirmar a exclusão de uma refeição do plano (Elite).
 *
 * Diz ANTES o que acontece: as outras refeições ficam como estão (nenhuma cresce para cobrir
 * a que saiu), e o que já foi registrado hoje nela sai junto. A última refeição não pode
 * sair: um plano vazio não tem de onde receber a próxima.
 */
export default function ExcluirRefeicao({API, indice, nome, dia, ultima, onExcluida, onFechar}) {
  const [excluindo, setExcluindo] = useState(false);
  const [erro, setErro] = useState("");

  const excluir = async () => {
    setExcluindo(true); setErro("");
    try {
      const r = await axios.delete(`${API}/nutrition/plan/meals/${indice}`, {params: {nome, dia}});
      if (!Array.isArray(r.data?.plan?.meals)) throw new Error("plano sem refeições");
      onExcluida(r.data.plan);
    } catch (e) {
      setErro(mensagemDeErro(e, "Não foi possível excluir a refeição. Tente de novo."));
    } finally { setExcluindo(false); }
  };

  return <ForgeDialog open onOpenChange={aberto => { if (!aberto) onFechar(); }} busy={excluindo}
                      title={`Excluir ${nome}?`} testId="excluir-refeicao"
                      description={ultima
                        ? "Esta é a única refeição do plano. Crie a nova antes de excluir esta."
                        : "A refeição sai do plano. As outras continuam como estão, nenhuma cresce para cobrir. O que você já registrou hoje nela também sai."}>
    <div className="meal-food-editor">
      {erro && <p role="alert">{erro}</p>}
      <button type="button" className="fg-btn fg-btn-cheio" data-testid="confirmar-exclusao"
              disabled={excluindo || ultima} aria-busy={excluindo} onClick={excluir}>
        {excluindo ? "Excluindo…" : "Excluir refeição"}
      </button>
      <button type="button" className="fg-btn fg-btn-2" disabled={excluindo} onClick={onFechar}>Cancelar</button>
    </div>
  </ForgeDialog>;
}
