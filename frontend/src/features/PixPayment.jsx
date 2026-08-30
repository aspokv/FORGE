import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { Check, Copy, ExternalLink, QrCode } from "lucide-react";

export default function PixPayment({ API, payment, onApproved, onClose }) {
  const [copiado, setCopiado] = useState(false);
  const [confirmando, setConfirmando] = useState(true);
  const aprovado = useRef(false);
  const aoAprovar = useRef(onApproved);

  useEffect(() => {
    aoAprovar.current = onApproved;
  }, [onApproved]);

  useEffect(() => {
    let vivo = true;
    const conferir = async () => {
      try {
        const r = await axios.get(`${API}/billing/me`);
        if (vivo && !aprovado.current && r.data.status === "active") {
          aprovado.current = true;
          setConfirmando(false);
          aoAprovar.current?.(r.data);
        }
      } catch (e) {
        // Conta ainda pendente ou deploy momentaneamente indisponivel: tenta novamente.
      }
    };
    conferir();
    const timer = setInterval(conferir, 3000);
    return () => { vivo = false; clearInterval(timer); };
  }, [API]);

  const copiar = async () => {
    if (!payment?.qr_code) return;
    try {
      await navigator.clipboard.writeText(payment.qr_code);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 2000);
    } catch (_) {
      setCopiado(false);
    }
  };

  return (
    <section className="pix-payment" data-testid="pix-payment">
      <div className="pix-payment-head">
        <div><p className="eyebrow">PAGAMENTO PIX</p><h3>Escaneie ou copie o código</h3></div>
        {onClose && <button type="button" className="text-button" onClick={onClose}>Voltar</button>}
      </div>
      {payment?.qr_code_base64 && (
        <img className="pix-qr" alt="QR Code PIX"
          src={`data:image/png;base64,${payment.qr_code_base64}`} />
      )}
      {payment?.qr_code && (
        <button type="button" className="secondary-button pix-copy" onClick={copiar}>
          {copiado ? <Check size={16} /> : <Copy size={16} />}
          {copiado ? "Código copiado" : "Copiar PIX Copia e Cola"}
        </button>
      )}
      {payment?.checkout_url && (
        <a className="text-button pix-external" href={payment.checkout_url}
          target="_blank" rel="noreferrer">
          <ExternalLink size={14} /> Abrir no Mercado Pago
        </a>
      )}
      <p className="pix-wait"><QrCode size={15} />
        {confirmando ? "Aguardando o pagamento. Esta tela libera o FORGE automaticamente." :
          "Pagamento confirmado. Liberando seu acesso..."}
      </p>
      <p className="muted">O QR Code vence em até 24 horas. Seus 30 dias começam somente após a confirmação.</p>
    </section>
  );
}
