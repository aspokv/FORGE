import { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import axios from "axios";
import { Activity, Check, ChevronRight } from "lucide-react";
import "./cardio-finisher.css";

const API = `${process.env.REACT_APP_BACKEND_URL || ""}/api`;
const MODALITIES = ["Caminhada", "Bike", "Elíptico", "Escada"];
const MINUTES = [10, 15, 20];
const RPE = [3, 4, 5, 6];

export function cardioRecommendation(sessionLabel = "") {
  const label = String(sessionLabel || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const lowerBody = /(legs|lower|perna|quadriceps|posterior|gluteo|panturrilha)/.test(label);
  if (lowerBody) {
    return {
      kind: "recovery",
      title: "Recuperação leve",
      subtitle: "Finalização opcional, sem competir com a sessão de pernas.",
      modality: "Bike",
      minutes: 10,
      rpe: 3,
    };
  }
  return {
    kind: "moderate",
    title: "Condicionamento moderado",
    subtitle: "Ritmo contínuo e confortável para fechar a sessão.",
    modality: "Caminhada",
    minutes: 15,
    rpe: 4,
  };
}

const token = () => `cardio-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;

export function CardioFinisher({ api = API, sessionLabel = "" }) {
  const recommendation = cardioRecommendation(sessionLabel);
  const [modality, setModality] = useState(recommendation.modality);
  const [minutes, setMinutes] = useState(recommendation.minutes);
  const [rpe, setRpe] = useState(recommendation.rpe);
  const [state, setState] = useState("idle");
  const [message, setMessage] = useState("");
  const clientToken = useRef(token());

  useEffect(() => {
    const next = cardioRecommendation(sessionLabel);
    setModality(next.modality);
    setMinutes(next.minutes);
    setRpe(next.rpe);
    setState("idle");
    setMessage("");
    clientToken.current = token();
  }, [sessionLabel]);

  const save = async () => {
    if (state === "saving" || state === "saved") return;
    setState("saving");
    setMessage("");
    try {
      await axios.post(`${api}/cardio`, {
        client_token: clientToken.current,
        kind: recommendation.kind,
        modality,
        minutes,
        rpe,
        session_label: sessionLabel,
        completed: true,
      });
      setState("saved");
      setMessage(`${modality} · ${minutes} min · RPE ${rpe} registrado.`);
    } catch {
      setState("error");
      setMessage("Não foi possível registrar o cardio agora. O treino principal continua salvo normalmente.");
    }
  };

  return (
    <section className="cardio-finisher" data-testid="cardio-finisher">
      <div className="cardio-finisher-head">
        <span className="cardio-finisher-icon"><Activity size={19} /></span>
        <div>
          <p className="eyebrow">CARDIO / FINALIZAÇÃO</p>
          <h3>{recommendation.title}</h3>
          <p>{recommendation.subtitle}</p>
        </div>
      </div>

      <div className="cardio-finisher-grid">
        <label>
          <span>MODALIDADE</span>
          <select value={modality} onChange={event => { setModality(event.target.value); setState("idle"); }} aria-label="Modalidade do cardio">
            {MODALITIES.map(item => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <div className="cardio-finisher-choice">
          <span>TEMPO</span>
          <div>{MINUTES.map(value => <button type="button" key={value} className={minutes === value ? "active" : ""} onClick={() => { setMinutes(value); setState("idle"); }}>{value} min</button>)}</div>
        </div>
        <div className="cardio-finisher-choice">
          <span>ESFORÇO PERCEBIDO</span>
          <div>{RPE.map(value => <button type="button" key={value} className={rpe === value ? "active" : ""} onClick={() => { setRpe(value); setState("idle"); }}>RPE {value}</button>)}</div>
        </div>
      </div>

      <div className="cardio-finisher-actions">
        <button type="button" className={state === "saved" ? "cardio-save saved" : "cardio-save"} disabled={state === "saving" || state === "saved"} onClick={save} data-testid="cardio-save">
          {state === "saved" ? <><Check size={17} /> Cardio registrado</> : state === "saving" ? "Registrando…" : <>Registrar cardio <ChevronRight size={17} /></>}
        </button>
        <small>Opcional. Não bloqueia a conclusão do treino.</small>
      </div>
      {message && <p className={`cardio-finisher-status ${state}`} role="status" data-testid="cardio-status">{message}</p>}
    </section>
  );
}

export function installCardioFinisher() {
  if (typeof document === "undefined" || typeof MutationObserver === "undefined") return () => {};
  let host = null;
  let root = null;
  let currentLabel = null;
  let scheduled = false;

  const unmount = () => {
    if (root) root.unmount();
    if (host?.isConnected) host.remove();
    host = null;
    root = null;
    currentLabel = null;
  };

  const sync = () => {
    scheduled = false;
    const live = document.querySelector(".workout-live-reference");
    const checkout = live?.querySelector(".session-checkout");
    if (!live || !checkout) {
      if (host) unmount();
      return;
    }
    const label = live.querySelector(".workout-head h2")?.textContent?.trim() || "Treino";
    if (!host || !host.isConnected) {
      host = document.createElement("div");
      host.id = "forge-cardio-finisher-host";
      checkout.parentNode.insertBefore(host, checkout);
      root = createRoot(host);
      currentLabel = null;
    }
    if (label !== currentLabel) {
      currentLabel = label;
      root.render(<CardioFinisher sessionLabel={label} />);
    }
  };

  const scheduleSync = () => {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(sync);
  };
  const observer = new MutationObserver(scheduleSync);
  observer.observe(document.body, { childList: true, subtree: true });
  sync();
  return () => { observer.disconnect(); unmount(); };
}
