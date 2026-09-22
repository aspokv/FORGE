import {AlertCircle, CheckCircle2, LoaderCircle} from "lucide-react";

export default function AsyncState({kind="loading", title, children, onRetry, busy=false}) {
  const Icon = kind === "error" ? AlertCircle : kind === "success" ? CheckCircle2 : LoaderCircle;
  return <div className={`forge-feedback forge-feedback-${kind}`} role={kind === "error" ? "alert" : "status"} aria-busy={busy || kind === "loading"}>
    <Icon size={20} aria-hidden="true"/>
    <div><strong>{title || (kind === "loading" ? "Carregando…" : "Não foi possível carregar")}</strong>{children && <p>{children}</p>}</div>
    {onRetry && <button type="button" onClick={onRetry} disabled={busy}>{busy ? "Tentando…" : "Tentar novamente"}</button>}
  </div>;
}
