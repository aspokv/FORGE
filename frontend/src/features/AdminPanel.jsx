import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import {mensagemDeErro} from "./mensagemDeErro";
import { motion } from "framer-motion";
import { Copy, Plus, ShieldCheck, RotateCcw, Ban, Check, X, LogOut, ChevronRight, ClipboardCopy, Users, Activity, ScrollText, CreditCard, Archive, ArchiveRestore, Trash2, AlertTriangle } from "lucide-react";
import { API, useAuth } from "./AuthContext";

// Os planos que existem de verdade, os mesmos de `billing_plans.py`. O painel oferecia
// FORGE_ACCESS, FORGE_PRO e LIFETIME, nomes de antes de existir cobranca, e o Elite nem
// aparecia — justamente o plano onde mora o Conselho.
export const PLANOS = [
  { code: "essential", nome: "FORGE Essencial", preco: "R$ 39,90/mês" },
  { code: "pro", nome: "FORGE Pro", preco: "R$ 69,90/mês" },
  { code: "elite", nome: "FORGE Elite", preco: "R$ 99,90/mês" },
];
export const NOME_DO_PLANO = Object.fromEntries(PLANOS.map(p => [p.code, p.nome]));

// O que a pessoa le no lugar do enum do banco. "PENDING_PAYMENT" nao cabia na pilula e
// vazava por cima da borda; alem de caber, isto e o que um humano entende.
export const ROTULO_DE_STATUS = {
  ACTIVE: "Ativo", PENDING: "Pendente", PENDING_PAYMENT: "Aguardando",
  SUSPENDED: "Suspenso", EXPIRED: "Expirado",
};

// De onde veio o acesso, para o administrador nao confundir cortesia com venda.
export const ROTULO_DA_ORIGEM = {
  admin: "administrador", courtesy: "cortesia", mercadopago: "assinatura",
};
const VALIDITIES = [
  { id: "30", label: "30 dias" },
  { id: "90", label: "90 dias" },
  { id: "180", label: "180 dias" },
  { id: "365", label: "1 ano" },
  { id: "LIFETIME", label: "Vitalício" },
  { id: "CUSTOM", label: "Personalizado" },
];

const STATUS_COLORS = { ACTIVE: "success", PENDING: "warn", PENDING_PAYMENT: "warn", SUSPENDED: "danger", EXPIRED: "danger" };

/**
 * O plano que a pessoa REALMENTE tem.
 *
 * A coluna mostrava `users.plan`, um campo que `resolver_acesso` nunca le: a tela dizia
 * "vitalicio" para uma conta bloqueada por falta de pagamento. Agora ela mostra o que o
 * backend usa para liberar ou negar, e de onde esse acesso veio.
 */
function PlanoDoAtleta({ acesso, id }) {
  const code = acesso?.plan_code;
  if (!code) {
    return (
      <span className="athlete-plano" data-testid={`athlete-plan-${id}`}>
        <b className="sem-plano">{acesso?.awaiting_payment ? "Aguardando pagamento" : "Sem plano"}</b>
      </span>
    );
  }
  return (
    <span className="athlete-plano" data-testid={`athlete-plan-${id}`}>
      <b>{NOME_DO_PLANO[code] || code}</b>
      <small>{ROTULO_DA_ORIGEM[acesso.source] || acesso.source || ""}</small>
    </span>
  );
}

function copyToClipboard(text) {
  if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(text);
  const t = document.createElement("textarea");
  t.value = text; document.body.appendChild(t); t.select();
  try { document.execCommand("copy"); } finally { document.body.removeChild(t); }
  return Promise.resolve();
}

function inviteFullUrl(inviteUrl) {
  return `${window.location.origin}${inviteUrl}`;
}

export default function AdminPanel() {
  const { user, signOut, navigate } = useAuth();
  const [stats, setStats] = useState(null);
  const [athletes, setAthletes] = useState([]);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [creator, setCreator] = useState(false);
  const [detail, setDetail] = useState(null);
  const [audit, setAudit] = useState([]);
  const [tab, setTab] = useState("athletes");
  const [flash, setFlash] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (q) params.q = q;
      if (status) params.status = status;
      const [s, a, al] = await Promise.all([
        axios.get(`${API}/admin/stats`),
        axios.get(`${API}/admin/athletes`, { params }),
        axios.get(`${API}/admin/audit-log?limit=60`),
      ]);
      setStats(s.data); setAthletes(a.data.athletes); setAudit(al.data.log);
    } catch (e) {
      setFlash({ type: "error", text: "Não foi possível carregar o painel." });
    } finally { setLoading(false); }
  }, [q, status]);

  useEffect(() => { load(); }, [load]);

  const notify = (type, text) => { setFlash({ type, text }); setTimeout(() => setFlash(null), 4000); };

  const onCreated = ({ athlete, invite_url }) => {
    setCreator(false);
    setAthletes(list => [athlete, ...list]);
    setDetail({ athlete, invite_url });
    notify("success", `Convite gerado para ${athlete.email}. Copie e envie por WhatsApp.`);
  };

  const suspend = async id => { await axios.post(`${API}/admin/athletes/${id}/suspend`); await load(); notify("success", "Atleta suspenso."); };
  const reactivate = async id => { await axios.post(`${API}/admin/athletes/${id}/reactivate`); await load(); notify("success", "Atleta reativado."); };
  const arquivar = async (id, arquivado) => {
    try {
      await axios.post(`${API}/admin/athletes/${id}/${arquivado ? "desarquivar" : "arquivar"}`,
                       arquivado ? undefined : {});
      notify("success", arquivado ? "Atleta de volta à lista." : "Atleta arquivado.");
      load();
    } catch (erro) {
      notify("error", mensagemDeErro(erro, "Não foi possível arquivar."));
    }
  };

  const requirePayment = async id => {
    try {
      await axios.post(`${API}/admin/athletes/${id}/require-payment`);
      await load();
      notify("success", "Conta liberada para escolher e comprar um novo plano.");
    } catch (e) {
      notify("error", mensagemDeErro(e, "Não foi possível liberar a nova assinatura."));
    }
  };
  const regen = async id => {
    const r = await axios.post(`${API}/admin/athletes/${id}/regenerate-invite`);
    notify("success", "Novo convite gerado.");
    setDetail(prev => (prev && prev.athlete.id === id ? { ...prev, invite_url: r.data.invite_url } : prev));
    load();
  };

  return (
    <div className="admin-shell" data-testid="admin-panel">
      <aside className="admin-rail">
        <div className="brand"><span className="brand-mark">F</span><span>FORGE</span></div>
        <p className="rail-caption">ADMIN CONSOLE</p>
        <nav>
          <button className={tab === "athletes" ? "nav-item active" : "nav-item"} data-testid="admin-tab-athletes" onClick={() => setTab("athletes")}><Users size={16} /> Atletas</button>
          <button className={tab === "audit" ? "nav-item active" : "nav-item"} data-testid="admin-tab-audit" onClick={() => setTab("audit")}><ScrollText size={16} /> Audit log</button>
          <button className="nav-item" data-testid="admin-open-app" onClick={() => navigate("/app")}><Activity size={16} /> Ver como atleta demo</button>
        </nav>
        <div className="rail-bottom">
          <div><ShieldCheck size={13} /> {user?.email}</div>
          <button className="text-button" data-testid="admin-logout" onClick={signOut}><LogOut size={14} /> Sair</button>
        </div>
      </aside>

      <main className="admin-main">
        <header className="topbar">
          <div>
            <p className="eyebrow">ADMIN · {new Date().toLocaleDateString("pt-BR", { day: "2-digit", month: "short", year: "numeric" }).toUpperCase()}</p>
            <h1>Console FORGE</h1>
          </div>
          <button className="primary-button" data-testid="open-create-athlete" onClick={() => setCreator(true)}><Plus size={16} /> Adicionar atleta</button>
        </header>

        {flash && <div className={`admin-flash ${flash.type}`} data-testid="admin-flash">{flash.text}</div>}

        <section className="admin-stats">
          <StatCard label="Total" value={stats?.total ?? "—"} testid="stat-total" />
          <StatCard label="Ativos" value={stats?.active ?? "—"} testid="stat-active" />
          <StatCard label="Pendentes" value={stats ? (stats.pending || 0) + (stats.pending_payment || 0) : "—"} testid="stat-pending" />
          <StatCard label="Suspensos" value={stats?.suspended ?? "—"} testid="stat-suspended" />
          <StatCard label="Novos no mês" value={stats?.new_this_month ?? "—"} testid="stat-new" />
          <StatCard label="IA hoje" value={stats?.ai_calls_today ?? "—"} testid="stat-ai" />
        </section>

        {tab === "athletes" && (
          <>
            <div className="admin-filters">
              <input placeholder="Buscar por nome ou e-mail" data-testid="admin-search" value={q} onChange={e => setQ(e.target.value)} />
              <select data-testid="admin-status-filter" value={status} onChange={e => setStatus(e.target.value)}>
                <option value="">Todos os status</option>
                <option value="PENDING">Pendentes</option>
                <option value="PENDING_PAYMENT">Aguardando pagamento</option>
                <option value="ACTIVE">Ativos</option>
                <option value="SUSPENDED">Suspensos</option>
                <option value="EXPIRED">Expirados</option>
                <option value="ARCHIVED">Arquivados</option>
              </select>
            </div>

            <section className="panel admin-table">
              {loading && <p className="muted">Carregando...</p>}
              {!loading && athletes.length === 0 && <p className="muted" data-testid="admin-empty">Nenhum atleta ainda. Clique em &quot;Adicionar atleta&quot; para começar.</p>}
              <div className="athlete-rows">
                {athletes.map(a => (
                  <div className="athlete-row" key={a.id} data-testid={`athlete-row-${a.id}`}>
                    <div className="athlete-main">
                      <b>{a.name}</b>
                      <span className="muted">{a.email}</span>
                    </div>
                    <span className={`badge ${STATUS_COLORS[a.status] || "muted"}`} data-testid={`athlete-status-${a.id}`}>{ROTULO_DE_STATUS[a.status] || a.status}</span>
                    <PlanoDoAtleta acesso={a.acesso} id={a.id} />
                    <span className="muted">{a.expires_at ? `até ${a.expires_at.slice(0, 10)}` : "vitalício"}</span>
                    <div className="athlete-actions">
                      <button className="ghost-button" data-testid={`view-athlete-${a.id}`} onClick={() => setDetail({ athlete: a })}>Ver</button>
                      {a.archived_at ? (
                        <button className="ghost-button" data-testid={`unarchive-athlete-${a.id}`}
                                onClick={() => arquivar(a.id, true)}>
                          <ArchiveRestore size={14} /> Restaurar
                        </button>
                      ) : (
                        <button className="ghost-button" data-testid={`archive-athlete-${a.id}`}
                                onClick={() => arquivar(a.id, false)}>
                          <Archive size={14} /> Arquivar
                        </button>
                      )}
                      {a.status === "SUSPENDED" ? (
                        <>
                          <button className="ghost-button" data-testid={`reactivate-athlete-${a.id}`} onClick={() => reactivate(a.id)}><Check size={14} /> Reativar</button>
                          <button className="ghost-button payment-action" data-testid={`require-payment-athlete-${a.id}`} onClick={() => requirePayment(a.id)}><CreditCard size={14} /> Liberar para comprar</button>
                        </>
                      ) : (
                        <button className="ghost-button" data-testid={`suspend-athlete-${a.id}`} onClick={() => suspend(a.id)}><Ban size={14} /> Suspender</button>
                      )}
                      <button className="ghost-button" data-testid={`regen-athlete-${a.id}`} onClick={() => regen(a.id)}><RotateCcw size={14} /> Convite</button>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </>
        )}

        {tab === "audit" && (
          <section className="panel">
            <p className="eyebrow">AUDIT LOG · ÚLTIMAS AÇÕES</p>
            {audit.length === 0 && <p className="muted">Nenhuma ação administrativa registrada ainda.</p>}
            <ul className="audit-list">
              {audit.map(a => (
                <li key={a.id} data-testid={`audit-row-${a.id}`}>
                  <span className="badge muted">{a.action}</span>
                  <b>{a.actor_email}</b>
                  <span className="muted">{a.target_user_id?.slice(0, 8) || ""}</span>
                  <time className="muted">{new Date(a.created_at).toLocaleString("pt-BR")}</time>
                </li>
              ))}
            </ul>
          </section>
        )}
      </main>

      {creator && <CreateAthleteModal onClose={() => setCreator(false)} onCreated={onCreated} />}
      {detail && <AthleteDetail data={detail} onClose={() => setDetail(null)} onChanged={load} onNotify={notify} />}
    </div>
  );
}

function StatCard({ label, value, testid }) {
  return (
    <div className="stat-card" data-testid={testid}>
      <span className="eyebrow">{label}</span>
      <b>{value}</b>
    </div>
  );
}

function CreateAthleteModal({ onClose, onCreated }) {
  // access_mode decide quem paga a conta. Cortesia exige confirmar e dizer por que:
  // o backend recusa sem isso, e o formulario nao deve deixar chegar la sem.
  const [form, setForm] = useState({
    email: "", name: "", validity: "30", custom_days: 60,
    admin_note: "", access_mode: "courtesy", confirm_courtesy: false,
    courtesy_reason: "", plan_code: "pro",
  });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async e => {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      const cortesia = form.access_mode === "courtesy";
      const payload = {
        ...form,
        custom_days: form.validity === "CUSTOM" ? Number(form.custom_days) : undefined,
        // Nao mandamos campos do outro modo: eles nao significam nada la, e mandar
        // "confirm_courtesy" num convite para assinar so confundiria a leitura do log.
        confirm_courtesy: cortesia ? form.confirm_courtesy : undefined,
        courtesy_reason: cortesia ? form.courtesy_reason : undefined,
        plan_code: cortesia ? undefined : form.plan_code,
      };
      const { data } = await axios.post(`${API}/admin/athletes`, payload);
      onCreated(data);
    } catch (e) {
      const detail = e.response?.data?.detail;
      if (typeof detail === "string") setErr(detail);
      else if (detail?.message) setErr(detail.message);
      else setErr("Não foi possível criar o atleta.");
    } finally { setBusy(false); }
  };
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));
  return (
    <div className="coach-overlay" data-testid="create-athlete-modal">
      <motion.div className="builder-panel" initial={{ x: 40, opacity: 0 }} animate={{ x: 0, opacity: 1 }}>
        <div className="coach-header">
          <div><p className="eyebrow">NOVO ATLETA</p><h2>Criar acesso</h2></div>
          <button className="icon-button" data-testid="close-create-athlete" onClick={onClose}><X size={20} /></button>
        </div>
        <form onSubmit={submit} className="create-athlete-form">
          <div className="field-grid">
            <label className="deep-field"><span>Nome</span><input data-testid="new-athlete-name" value={form.name} onChange={e => set("name", e.target.value)} required /></label>
            <label className="deep-field"><span>E-mail</span><input data-testid="new-athlete-email" type="email" value={form.email} onChange={e => set("email", e.target.value)} required /></label>
          </div>
          <label className="deep-field">
            <span>Como esta pessoa entra</span>
            <select data-testid="new-athlete-access-mode" value={form.access_mode} onChange={e => set("access_mode", e.target.value)}>
              <option value="courtesy">Conceder acesso cortesia</option>
              <option value="subscription">Convidar para assinar</option>
            </select>
          </label>
          <label className="deep-field">
            <span>{form.access_mode === "courtesy" ? "Plano concedido" : "Plano sugerido"}</span>
            <select data-testid="new-athlete-plan-code" value={form.plan_code} onChange={e => set("plan_code", e.target.value)}>
              {PLANOS.map(p => <option key={p.code} value={p.code}>{p.nome} — {p.preco}</option>)}
            </select>
          </label>
          {form.access_mode === "courtesy" && (
            <>
              <label className="deep-field">
                <span>Motivo da cortesia</span>
                <input data-testid="new-athlete-courtesy-reason" value={form.courtesy_reason}
                       onChange={e => set("courtesy_reason", e.target.value)}
                       placeholder="Ex.: parceria de divulgação" required />
              </label>
              <label className="deep-field checkbox-row">
                <input type="checkbox" data-testid="new-athlete-confirm-courtesy"
                       checked={form.confirm_courtesy}
                       onChange={e => set("confirm_courtesy", e.target.checked)} />
                <span>Confirmo conceder acesso gratuito, sem cobrança, por minha decisão.</span>
              </label>
            </>
          )}
          <label className="deep-field">
            <span>Validade</span>
            <select data-testid="new-athlete-validity" value={form.validity} onChange={e => set("validity", e.target.value)}>
              {VALIDITIES.map(v => <option key={v.id} value={v.id}>{v.label}</option>)}
            </select>
          </label>
          {form.validity === "CUSTOM" && (
            <label className="deep-field"><span>Dias personalizados</span><input data-testid="new-athlete-custom-days" type="number" min="1" value={form.custom_days} onChange={e => set("custom_days", e.target.value)} /></label>
          )}
          <label className="deep-field"><span>Observação administrativa</span><input data-testid="new-athlete-note" value={form.admin_note} onChange={e => set("admin_note", e.target.value)} placeholder="Opcional" /></label>
          {err && <div className="auth-error">{err}</div>}
          <div className="builder-actions">
            <button className="secondary-button" type="button" data-testid="cancel-create-athlete" onClick={onClose}>Cancelar</button>
            <button className="primary-button" type="submit" data-testid="submit-create-athlete"
                    disabled={busy || (form.access_mode === "courtesy" && !form.confirm_courtesy)}>
              {busy ? "Criando..." : form.access_mode === "courtesy" ? "Conceder cortesia" : "Convidar para assinar"} <ChevronRight size={16} />
            </button>
          </div>
        </form>
      </motion.div>
    </div>
  );
}

export function AthleteDetail({ data, onClose, onChanged, onNotify }) {
  const [full, setFull] = useState(null);
  const [inviteUrl, setInviteUrl] = useState(data.invite_url || "");
  const [edit, setEdit] = useState({ validity: "", custom_days: 60, name: data.athlete.name });
  const [plano, setPlano] = useState({ code: "", motivo: "", busy: false, erro: "", confirmarPago: null });
  const [exclusao, setExclusao] = useState({ aberta: false, email: "", motivo: "", busy: false, erro: "" });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    axios.get(`${API}/admin/athletes/${data.athlete.id}`).then(r => setFull(r.data));
  }, [data.athlete.id]);

  const copy = async v => { await copyToClipboard(v); onNotify("success", "Copiado para a área de transferência."); };

  const save = async () => {
    setBusy(true);
    try {
      const payload = {};
      if (edit.name !== data.athlete.name) payload.name = edit.name;
      if (edit.validity) { payload.validity = edit.validity; if (edit.validity === "CUSTOM") payload.custom_days = Number(edit.custom_days); }
      if (!Object.keys(payload).length) { onNotify("success", "Sem mudanças."); return; }
      await axios.patch(`${API}/admin/athletes/${data.athlete.id}`, payload);
      onChanged();
      onNotify("success", "Atleta atualizado.");
    } finally { setBusy(false); }
  };

  const acessoAtual = full?.acesso || data.athlete.acesso;

  /**
   * Concede o plano.
   *
   * `substituir === true` e literal de proposito. A primeira versao passava esta funcao
   * direto para `onClick`, entao o React entregava o EVENTO DO CLIQUE como primeiro
   * argumento: `substituir` virava um SyntheticEvent, o axios tentava serializar um
   * objeto com referencia circular, e a requisicao **nunca saia**. O plano ficava como
   * estava e nenhum aviso aparecia perto do botao.
   *
   * A comparacao estrita fecha os dois lados: alem de nao quebrar, ela impede que um
   * valor truthy qualquer vire "sim, sobrescreva a assinatura paga", que e a direcao
   * perigosa desta chamada.
   */
  const concederPlano = async (substituir = false) => {
    setPlano(p => ({ ...p, busy: true, erro: "", confirmarPago: null }));
    try {
      const revogar = plano.code === "__revogar";
      const r = await axios.post(`${API}/admin/athletes/${data.athlete.id}/plano`, {
        plan_code: revogar ? null : plano.code,
        motivo: plano.motivo,
        substituir_assinatura_paga: substituir === true,
      });
      setFull(f => (f ? { ...f, acesso: r.data.acesso || { plan_code: null } } : f));
      setPlano({ code: "", motivo: "", busy: false, erro: "", confirmarPago: null });
      onChanged();
      onNotify("success", revogar ? "Cortesia removida." : "Plano concedido.");
    } catch (erro) {
      const detalhe = erro?.response?.data?.detail;
      // Uma assinatura PAGA nao e sobrescrita por acidente. Isto era um `window.confirm`,
      // que o navegador pode bloquear e que nenhum teste consegue acionar; agora a
      // pergunta fica na propria tela, onde da para ler o que se esta trocando.
      if (detalhe?.reason === "paid_subscription") {
        setPlano(p => ({ ...p, busy: false, confirmarPago: detalhe.message }));
        return;
      }
      // O erro mora AO LADO do botao. Ele ia para a faixa do topo, que some em quatro
      // segundos e fica longe da acao: na pratica a tela simplesmente nao respondia.
      setPlano(p => ({ ...p, busy: false,
        erro: mensagemDeErro(erro, "Não foi possível aplicar o plano.") }));
    }
  };

  /**
   * Exclusao definitiva.
   *
   * O e-mail digitado vai para o servidor e e ELE quem compara. A tela poderia comparar
   * sozinha e evitar a viagem, mas ai a trava viveria no lugar errado: quem chama a API
   * direto passaria por cima dela. Aqui a tela so nao deixa clicar a toa.
   */
  const excluir = async () => {
    setExclusao(e => ({ ...e, busy: true, erro: "" }));
    try {
      const r = await axios.delete(`${API}/admin/athletes/${data.athlete.id}`, {
        data: { confirmar_email: exclusao.email, motivo: exclusao.motivo },
      });
      onNotify("success", `Atleta excluído. ${r.data.total} registros removidos.`);
      onChanged();
      onClose();
    } catch (erro) {
      setExclusao(e => ({ ...e, busy: false,
        erro: mensagemDeErro(erro, "Não foi possível excluir.") }));
    }
  };

  const regen = async () => {
    const r = await axios.post(`${API}/admin/athletes/${data.athlete.id}/regenerate-invite`);
    setInviteUrl(r.data.invite_url);
    onNotify("success", "Novo convite gerado.");
    onChanged();
  };

  return (
    <div className="coach-overlay" data-testid="athlete-detail-modal">
      <motion.div className="builder-panel" initial={{ x: 40, opacity: 0 }} animate={{ x: 0, opacity: 1 }}>
        <div className="coach-header">
          <div><p className="eyebrow">ATLETA</p><h2>{data.athlete.name}</h2></div>
          <button className="icon-button" data-testid="close-athlete-detail" onClick={onClose}><X size={20} /></button>
        </div>
        <p className="muted">
          {data.athlete.email} · Status <b>{ROTULO_DE_STATUS[data.athlete.status] || data.athlete.status}</b>
          {" · "}
          {acessoAtual?.plan_code ? (
            <>
              Plano <b data-testid="detail-plan">{NOME_DO_PLANO[acessoAtual.plan_code] || acessoAtual.plan_code}</b>
              {acessoAtual.source ? ` (${ROTULO_DA_ORIGEM[acessoAtual.source] || acessoAtual.source})` : ""}
            </>
          ) : (
            <b data-testid="detail-plan">{acessoAtual?.awaiting_payment ? "Aguardando pagamento" : "Sem plano"}</b>
          )}
        </p>
        {full && (
          <div className="athlete-metrics">
            <div><b>{full.workouts}</b><span>séries registradas</span></div>
            <div><b>{full.profile?.days || 0}</b><span>dias planejados</span></div>
            <div><b>{full.profile?.priorities?.length || 0}</b><span>prioridades</span></div>
          </div>
        )}

        {inviteUrl && (
          <div className="invite-box" data-testid="invite-box">
            <p className="eyebrow">LINK DE CONVITE (14 dias)</p>
            <div className="invite-link">
              <code data-testid="invite-link">{inviteFullUrl(inviteUrl)}</code>
              <button className="ghost-button" data-testid="copy-invite" onClick={() => copy(inviteFullUrl(inviteUrl))}><ClipboardCopy size={14} /> Copiar</button>
            </div>
            <p className="muted">Envie por WhatsApp. O atleta define a própria senha ao abrir.</p>
          </div>
        )}

        <div className="admin-edit">
          <label className="deep-field"><span>Nome</span><input data-testid="edit-athlete-name" value={edit.name || ""} onChange={e => setEdit({ ...edit, name: e.target.value })} /></label>
          <label className="deep-field">
            <span>Alterar validade</span>
            <select data-testid="edit-athlete-validity" value={edit.validity} onChange={e => setEdit({ ...edit, validity: e.target.value })}>
              <option value="">Manter</option>
              {VALIDITIES.map(v => <option key={v.id} value={v.id}>{v.label}</option>)}
            </select>
          </label>
          {edit.validity === "CUSTOM" && (
            <label className="deep-field"><span>Dias personalizados</span><input data-testid="edit-athlete-custom-days" type="number" value={edit.custom_days} onChange={e => setEdit({ ...edit, custom_days: e.target.value })} /></label>
          )}
        </div>

        <div className="conceder-plano" data-testid="conceder-plano">
          <h4>Conceder plano</h4>
          <p>
            Cortesia é acesso concedido, não pagamento: valor zero, sem cobrança e fora de
            qualquer relatório de receita. Fica registrado quem concedeu, quando e por quê.
          </p>
          <div className="linha">
            <select data-testid="conceder-plano-code" value={plano.code}
                    onChange={e => setPlano({ ...plano, code: e.target.value })}>
              <option value="">Escolher plano...</option>
              {PLANOS.map(p => <option key={p.code} value={p.code}>{p.nome}</option>)}
              <option value="__revogar">Remover a cortesia</option>
            </select>
            <input data-testid="conceder-plano-motivo" value={plano.motivo}
                   onChange={e => setPlano({ ...plano, motivo: e.target.value })}
                   placeholder="Motivo (ex.: conta de demonstração)" />
          </div>
          {plano.confirmarPago ? (
            <div className="conceder-confirmar" data-testid="conceder-plano-confirmar">
              <p>{plano.confirmarPago}</p>
              <div className="linha">
                <button className="secondary-button" data-testid="conceder-plano-cancelar"
                        onClick={() => setPlano(p => ({ ...p, confirmarPago: null }))}>
                  Cancelar
                </button>
                <button className="primary-button" data-testid="conceder-plano-substituir"
                        onClick={() => concederPlano(true)} disabled={plano.busy}>
                  Substituir mesmo assim
                </button>
              </div>
            </div>
          ) : (
            <button className="primary-button" data-testid="conceder-plano-salvar"
                    onClick={() => concederPlano(false)} disabled={plano.busy || !plano.code}>
              <ShieldCheck size={15} /> {plano.busy ? "Aplicando..." : "Aplicar plano"}
            </button>
          )}
          {plano.erro ? (
            <p className="conceder-erro" data-testid="conceder-plano-erro" role="alert">
              {plano.erro}
            </p>
          ) : null}
        </div>

        <div className="area-de-risco" data-testid="area-de-risco">
          {!exclusao.aberta ? (
            <button className="ghost-button perigo" data-testid="abrir-exclusao"
                    onClick={() => setExclusao({ aberta: true, email: "", motivo: "", busy: false, erro: "" })}>
              <Trash2 size={14} /> Excluir definitivamente
            </button>
          ) : (
            <div className="exclusao-confirmar">
              {/* O texto vai dentro de um <span> proprio: sem ele, o <b> vira um item
                  do flex e a frase se parte em colunas no meio. */}
              <p className="exclusao-alerta">
                <AlertTriangle size={15} />
                <span>
                  Isto apaga a pessoa e tudo que é dela: treinos, séries, alimentação,
                  pesagens e fotos. <b>Não tem volta.</b> Para só tirar da lista, use
                  Arquivar.
                </span>
              </p>
              <label className="deep-field">
                <span>Digite {data.athlete.email} para confirmar</span>
                <input data-testid="exclusao-email" value={exclusao.email} autoComplete="off"
                       onChange={e => setExclusao(x => ({ ...x, email: e.target.value }))} />
              </label>
              <label className="deep-field">
                <span>Motivo (fica na auditoria)</span>
                <input data-testid="exclusao-motivo" value={exclusao.motivo}
                       onChange={e => setExclusao(x => ({ ...x, motivo: e.target.value }))}
                       placeholder="Ex.: conta de teste" />
              </label>
              {exclusao.erro ? (
                <p className="conceder-erro" data-testid="exclusao-erro" role="alert">{exclusao.erro}</p>
              ) : null}
              <div className="linha">
                <button className="secondary-button" data-testid="exclusao-cancelar"
                        onClick={() => setExclusao({ aberta: false, email: "", motivo: "", busy: false, erro: "" })}>
                  Cancelar
                </button>
                <button className="botao-perigo" data-testid="exclusao-confirmar"
                        onClick={excluir} disabled={exclusao.busy || !exclusao.email.trim()}>
                  <Trash2 size={15} /> {exclusao.busy ? "Excluindo..." : "Excluir para sempre"}
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="builder-actions">
          <button className="secondary-button" data-testid="regen-athlete-detail" onClick={regen}><RotateCcw size={14} /> Gerar novo convite</button>
          <button className="primary-button" data-testid="save-athlete-detail" onClick={save} disabled={busy}><Check size={16} /> {busy ? "Salvando..." : "Salvar mudanças"}</button>
        </div>
      </motion.div>
    </div>
  );
}
