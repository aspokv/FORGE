import { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { Check, Clock3, CreditCard, QrCode, ShieldCheck, Sparkles } from "lucide-react";
import PixPayment from "./PixPayment";

/**
 * Planos e assinatura.
 *
 * O preco e o plano vem SEMPRE do backend: esta tela envia apenas o codigo do plano no
 * checkout. Nada de valor, moeda ou id do Mercado Pago sai daqui — quem decide isso e a
 * allow-list do servidor.
 *
 * O retorno do checkout NAO libera acesso. A tela de retorno so consulta o estado; quem
 * ativa o plano e o webhook, depois de confirmar a assinatura na API do Mercado Pago.
 */

const brl = (v) =>
  typeof v === "number" ? v.toFixed(2).replace(".", ",") : "--";

const ROTULO_DE_ESTADO = {
  active: "Ativa",
  pending: "Aguardando confirmação",
  past_due: "Pagamento pendente",
  paused: "Pausada",
  cancelled: "Cancelada",
  expired: "Expirada",
  rejected: "Pagamento recusado",
};

function CardDePlano({ plano, atual, destaque, onAssinar, onPix, ocupado }) {
  return (
    <section
      className={`plan-card${destaque ? " recommended" : ""}${atual ? " current" : ""}`}
      data-testid={`plan-${plano.code}`}
    >
      {destaque && <span className="plan-flag">Recomendado</span>}
      {atual && <span className="plan-flag current">Seu plano</span>}

      <p className="eyebrow">{plano.nome}</p>
      <p className="plan-price">
        <span className="plan-currency">R$</span>
        <b>{brl(plano.preco)}</b>
        <small>/mês</small>
      </p>
      <p className="plan-billing">{plano.cobranca}</p>

      <p className="plan-audience">{plano.para_quem}</p>

      <ul className="plan-features">
        {plano.recursos.map((r) => (
          <li key={r}><Check size={13} /> <span>{r}</span></li>
        ))}
      </ul>

      {plano.em_breve?.length > 0 && (
        <div className="plan-soon" data-testid={`plan-soon-${plano.code}`}>
          <p className="eyebrow">Em breve</p>
          <ul>
            {plano.em_breve.map((r) => (
              <li key={r}><Clock3 size={12} /> <span>{r}</span></li>
            ))}
          </ul>
        </div>
      )}

      <div className="payment-options">
        <button className={destaque ? "primary-button plan-cta" : "secondary-button plan-cta"}
          data-testid={`subscribe-${plano.code}`} disabled={Boolean(ocupado) || atual}
          onClick={() => onAssinar(plano.code)}>
          <CreditCard size={15} /> {atual ? "Plano atual" : ocupado === "card" ? "Abrindo..." : "Cartão automático"}
        </button>
        {!atual && <button className="secondary-button plan-cta" data-testid={`pix-${plano.code}`}
          disabled={Boolean(ocupado)} onClick={() => onPix(plano.code)}>
          <QrCode size={15} /> {ocupado === "pix" ? "Gerando PIX..." : "PIX — 30 dias"}
        </button>}
      </div>
    </section>
  );
}

export default function Billing({ API }) {
  const [planos, setPlanos] = useState([]);
  const [assinatura, setAssinatura] = useState(null);
  const [carregando, setCarregando] = useState(true);
  const [ocupado, setOcupado] = useState("");
  const [erro, setErro] = useState("");
  const [aviso, setAviso] = useState("");
  const [pix, setPix] = useState(null);
  // Trava sincrona: dois toques no mesmo tick nao podem abrir dois checkouts.
  const trava = useRef(false);

  const carregar = useCallback(async () => {
    try {
      const [p, minha] = await Promise.all([
        axios.get(`${API}/billing/plans`),
        axios.get(`${API}/billing/me`).catch(() => null),
      ]);
      setPlanos(p.data.plans || []);
      if (minha) setAssinatura(minha.data);
    } catch (e) {
      console.error("[FORGE billing] carga falhou:", e?.response?.status, e?.response?.data ?? e);
      setErro("Não foi possível carregar os planos agora.");
    } finally {
      setCarregando(false);
    }
  }, [API]);

  useEffect(() => { carregar(); }, [carregar]);

  // Retorno do checkout: a URL traz o marcador, mas ele NAO ativa nada — apenas leva a
  // tela de confirmacao e recarrega o estado real vindo do backend.
  useEffect(() => {
    if (window.location.pathname.includes("/assinatura/retorno")) {
      setAviso("Estamos confirmando sua assinatura com o Mercado Pago.");
      const t = setTimeout(carregar, 4000);
      return () => clearTimeout(t);
    }
  }, [carregar]);

  const assinar = async (code) => {
    if (trava.current) return;
    trava.current = true;
    setOcupado(code); setErro("");
    try {
      const r = await axios.post(`${API}/billing/checkout`, { plan_code: code });
      window.location.href = r.data.checkout_url;
    } catch (e) {
      trava.current = false;
      setOcupado("");
      const detalhe = e?.response?.data?.detail;
      console.error("[FORGE billing] checkout falhou:", e?.response?.status, detalhe ?? e);
      setErro(detalhe?.message || (typeof detalhe === "string" ? detalhe : "")
        || "Não foi possível iniciar a assinatura agora.");
    }
  };

  const pagarPix = async (code) => {
    if (trava.current) return;
    trava.current = true;
    setOcupado(`${code}:pix`); setErro("");
    try {
      const r = await axios.post(`${API}/billing/pix`, { plan_code: code });
      setPix(r.data);
      trava.current = false; setOcupado("");
    } catch (e) {
      trava.current = false; setOcupado("");
      const detalhe = e?.response?.data?.detail;
      setErro(detalhe?.message || (typeof detalhe === "string" ? detalhe : "")
        || "Não foi possível gerar o PIX agora.");
    }
  };

  const cancelar = async () => {
    setOcupado("cancel"); setErro("");
    try {
      const r = await axios.post(`${API}/billing/cancel`);
      setAssinatura(r.data);
      setAviso("Assinatura cancelada. Seu acesso segue até o fim do período pago.");
    } catch (e) {
      const detalhe = e?.response?.data?.detail;
      console.error("[FORGE billing] cancelamento falhou:", e?.response?.status, detalhe ?? e);
      setErro(detalhe?.message || "Não foi possível cancelar agora.");
    } finally { setOcupado(""); }
  };

  if (carregando) {
    return <div className="content"><div className="skeleton-block" style={{ height: 120 }} /></div>;
  }

  const cortesia = assinatura?.grandfathered;
  const temAssinatura = assinatura?.provider_subscription_id
    && ["active", "past_due", "paused"].includes(assinatura.status);

  return (
    <div className="content billing-page">
      <div className="section-intro">
        <p className="eyebrow">ASSINATURA</p>
        <h2>Escolha como o FORGE trabalha para você.</h2>
        <p className="muted">Cobrança mensal recorrente. Cancele quando quiser.</p>
      </div>

      {aviso && <div className="notice" data-testid="billing-notice">{aviso}</div>}
      {erro && <div className="auth-error" data-testid="billing-error">{erro}</div>}
      {pix && <PixPayment API={API} payment={pix} onClose={() => setPix(null)}
        onApproved={() => { setPix(null); carregar(); }} />}

      {assinatura && (
        <section className="panel subscription-panel" data-testid="my-subscription">
          <div className="panel-top">
            <div>
              <p className="eyebrow">MINHA ASSINATURA</p>
              <h3>{assinatura.plan_name || "Sem plano"}</h3>
              {assinatura.para_quem && <p className="muted">{assinatura.para_quem}</p>}
            </div>
            <span className={`sub-state ${assinatura.status || ""}`}>
              {ROTULO_DE_ESTADO[assinatura.status] || "—"}
            </span>
          </div>

          <div className="sub-grid">
            <div><span>Valor</span><b>{assinatura.price ? `R$ ${brl(assinatura.price)}/mês` : "—"}</b></div>
            <div><span>{assinatura.payment_method === "pix" ? "Válido até" : "Próxima cobrança"}</span><b>{assinatura.next_charge?.slice(0, 10) || "—"}</b></div>
            <div><span>Origem</span><b>{cortesia ? "Cortesia" : assinatura.payment_method === "pix" ? "PIX — Mercado Pago" : "Mercado Pago"}</b></div>
          </div>

          {cortesia && (
            <p className="muted sub-courtesy">
              <ShieldCheck size={14} /> Seu acesso atual está garantido como cortesia — nada muda
              para você agora.
            </p>
          )}
          {assinatura.status === "past_due" && (
            <p className="notice" data-testid="past-due-notice">
              Não conseguimos confirmar a renovação. Seu acesso continua por alguns dias
              enquanto você atualiza o pagamento no Mercado Pago.
            </p>
          )}

          {temAssinatura && (
            <div className="action-row" style={{ marginTop: 16 }}>
              <button className="secondary-button" data-testid="cancel-subscription"
                disabled={ocupado === "cancel"} onClick={cancelar}>
                {ocupado === "cancel" ? "Cancelando..." : "Cancelar assinatura"}
              </button>
            </div>
          )}
        </section>
      )}

      <div className="plan-grid" data-testid="plan-grid">
        {planos.map((p) => (
          <CardDePlano
            key={p.code}
            plano={p}
            destaque={p.recomendado}
            atual={!cortesia && assinatura?.plan_code === p.code && assinatura?.status === "active"}
            ocupado={ocupado === p.code ? "card" : ocupado === `${p.code}:pix` ? "pix" : ""}
            onAssinar={assinar}
            onPix={pagarPix}
          />
        ))}
      </div>

      <p className="muted plan-footnote">
        <Sparkles size={13} /> O pagamento acontece no ambiente do Mercado Pago. O FORGE
        não recebe nem armazena os dados do seu cartão. No PIX, o acesso vale 30 dias e
        a renovação é feita com um novo pagamento.
      </p>
    </div>
  );
}
