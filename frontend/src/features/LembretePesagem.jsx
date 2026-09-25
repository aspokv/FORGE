import {useEffect, useState} from "react";
import axios from "axios";
import "./lembrete-pesagem.css";

/**
 * Lembrete da pesagem de sexta-feira, na tela inicial.
 *
 * A balança é o dado que decide a semana: é com ela que a periodização da dieta segura um
 * degrau e que o Conselho lê o ritmo. Uma pesagem por semana, sempre no mesmo dia e do
 * mesmo jeito, basta — e três sextas seguidas já dão a tendência que os dois precisam.
 *
 * Quando aparece: na sexta, até a pessoa pesar. Se a sexta passou sem pesagem, nos dias
 * seguintes, até ela registrar. Fora disso, some — lembrete que aparece todo dia vira
 * paisagem e ninguém mais lê.
 */
const SEXTA = 5;

export function chaveDoDia(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function ultimaSexta(hoje) {
  const d = new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate());
  d.setDate(d.getDate() - ((d.getDay() - SEXTA + 7) % 7));
  return d;
}

/** "sexta" | "atrasada" | null. `ultimaPesagem` é a data ISO da pesagem mais recente. */
export function motivoDoLembrete(hoje, ultimaPesagem) {
  const sexta = chaveDoDia(ultimaSexta(hoje));
  const ultima = ultimaPesagem ? String(ultimaPesagem).slice(0, 10) : null;
  if (ultima && ultima >= sexta) return null;
  return hoje.getDay() === SEXTA ? "sexta" : "atrasada";
}

export default function LembretePesagem({API, hoje = new Date()}) {
  const [estado, setEstado] = useState("carregando");
  const [ultima, setUltima] = useState(null);
  const [peso, setPeso] = useState("");
  const [erro, setErro] = useState("");
  const [salvo, setSalvo] = useState(null);

  useEffect(() => {
    let vivo = true;
    axios.get(`${API}/nutrition/weight`)
      .then(r => { if (!vivo) return; const h = r.data?.history || []; setUltima(h[0] || null); setEstado("pronto"); })
      .catch(() => { if (vivo) setEstado("indisponivel"); });
    return () => { vivo = false; };
  }, [API]);

  if (salvo) {
    return <p className="lembrete-pesagem lembrete-pesagem-ok" role="status" data-testid="pesagem-registrada">
      Pesagem registrada: {salvo.toLocaleString("pt-BR")} kg. Até a próxima sexta.
    </p>;
  }
  if (estado !== "pronto") return null;
  const motivo = motivoDoLembrete(hoje, ultima?.date);
  if (!motivo) return null;

  const valor = Number(String(peso).replace(",", "."));
  const valido = Number.isFinite(valor) && valor > 20 && valor <= 300;
  const registrar = async e => {
    e.preventDefault();
    if (!valido || estado === "salvando") return;
    setEstado("salvando"); setErro("");
    try {
      await axios.post(`${API}/nutrition/weight`, {weight_kg: valor, date: chaveDoDia(hoje)});
      setSalvo(valor);
    } catch {
      setErro("Não foi possível registrar agora. Seu número continua aqui; tente de novo.");
      setEstado("pronto");
    }
  };

  return <form className="lembrete-pesagem" data-testid="lembrete-pesagem" onSubmit={registrar}>
    <div>
      <strong>{motivo === "sexta" ? "Hoje é dia de pesagem" : "A pesagem de sexta ficou para trás"}</strong>
      <small>
        {motivo === "sexta" ? "De manhã, em jejum, depois do banheiro. " : "Registre hoje, do mesmo jeito de sempre. "}
        É com ela que o FORGE decide o ajuste da semana.
      </small>
    </div>
    <label className="lembrete-pesagem-campo">
      <span className="forge-home-sr-only">Seu peso em kg</span>
      <input type="text" inputMode="decimal" placeholder={ultima?.weight_kg ? String(ultima.weight_kg).replace(".", ",") : "83,5"}
             value={peso} data-testid="lembrete-pesagem-peso" disabled={estado === "salvando"}
             onChange={e => { setPeso(e.target.value); setErro(""); }}/>
      <span aria-hidden="true">kg</span>
    </label>
    <button type="submit" className="fg-btn fg-btn-cheio" data-testid="lembrete-pesagem-salvar"
            disabled={!valido || estado === "salvando"}>
      {estado === "salvando" ? "Registrando…" : "Registrar peso"}
    </button>
    {erro && <p className="fg-erro" role="alert">{erro}</p>}
  </form>;
}
