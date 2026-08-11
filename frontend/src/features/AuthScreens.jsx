import { useEffect, useState } from "react";
import axios from "axios";
import { motion } from "framer-motion";
import { ChevronRight, KeyRound, Mail, ShieldCheck, LockKeyhole, LogIn } from "lucide-react";
import { API, useAuth } from "./AuthContext";

function formatError(detail) {
  if (!detail) return "Falha na operação. Tente novamente.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map(e => e?.msg || JSON.stringify(e)).join(" ");
  return String(detail);
}

export function LoginScreen() {
  const { signIn, navigate } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async e => {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      const { data } = await axios.post(`${API}/auth/login`, { email: email.trim().toLowerCase(), password });
      signIn(data.token, data.user);
      navigate(data.user.role === "SUPER_ADMIN" ? "/admin" : "/app", true);
    } catch (e) {
      setErr(formatError(e.response?.data?.detail));
    } finally { setBusy(false); }
  };

  return (
    <div className="auth-shell" data-testid="login-screen">
      <div className="auth-brand"><span className="brand-mark">F</span><span>FORGE</span><small>ADVANCED TRAINING OS</small></div>
      <motion.form className="auth-card" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} onSubmit={submit}>
        <p className="eyebrow">ACESSO</p>
        <h1>Bem-vindo de volta.</h1>
        <p className="muted">Entre com seu e-mail e senha do FORGE.</p>
        <label className="deep-field">
          <span>E-mail</span>
          <input data-testid="login-email" type="email" autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} required />
        </label>
        <label className="deep-field">
          <span>Senha</span>
          <input data-testid="login-password" type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required />
        </label>
        {err && <div className="auth-error" data-testid="login-error">{err}</div>}
        <button className="primary-button auth-submit" data-testid="login-submit" disabled={busy} type="submit">
          <LogIn size={16} /> {busy ? "Entrando..." : "Entrar"} <ChevronRight size={16} />
        </button>
        <p className="auth-hint muted"><ShieldCheck size={13} /> Acesso apenas para atletas convidados.</p>
      </motion.form>
    </div>
  );
}

export function InviteScreen({ token }) {
  const { signIn, navigate } = useAuth();
  const [invite, setInvite] = useState(null);
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [confirm, setConfirm] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    axios.get(`${API}/auth/invite/${token}`).then(r => { setInvite(r.data); setName(r.data.name || ""); }).catch(e => setErr(formatError(e.response?.data?.detail) || "Convite inválido"));
  }, [token]);

  const submit = async e => {
    e.preventDefault();
    if (password.length < 8) { setErr("A senha precisa ter no mínimo 8 caracteres."); return; }
    if (password !== confirm) { setErr("As senhas não coincidem."); return; }
    setBusy(true); setErr("");
    try {
      const { data } = await axios.post(`${API}/auth/accept-invite`, { token, password, name });
      signIn(data.token, data.user);
      navigate(data.user.role === "SUPER_ADMIN" ? "/admin" : "/app", true);
    } catch (e) {
      setErr(formatError(e.response?.data?.detail));
    } finally { setBusy(false); }
  };

  if (err && !invite) return <div className="auth-shell"><div className="auth-card"><p className="eyebrow">CONVITE</p><h1>Convite indisponível.</h1><p className="muted">{err}</p></div></div>;
  if (!invite) return <div className="auth-shell"><div className="auth-card"><p className="muted">Carregando convite...</p></div></div>;

  return (
    <div className="auth-shell" data-testid="invite-screen">
      <div className="auth-brand"><span className="brand-mark">F</span><span>FORGE</span><small>NOVO ACESSO</small></div>
      <motion.form className="auth-card" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} onSubmit={submit}>
        <p className="eyebrow">CONVITE · {invite.plan}</p>
        <h1>Ative sua conta.</h1>
        <p className="muted">E-mail vinculado: <b>{invite.email}</b></p>
        <label className="deep-field">
          <span>Como quer ser chamado(a)?</span>
          <input data-testid="invite-name" value={name} onChange={e => setName(e.target.value)} />
        </label>
        <label className="deep-field">
          <span>Nova senha (mín. 8)</span>
          <input data-testid="invite-password" type="password" value={password} onChange={e => setPassword(e.target.value)} required />
        </label>
        <label className="deep-field">
          <span>Confirmar senha</span>
          <input data-testid="invite-confirm" type="password" value={confirm} onChange={e => setConfirm(e.target.value)} required />
        </label>
        {err && <div className="auth-error" data-testid="invite-error">{err}</div>}
        <button className="primary-button auth-submit" data-testid="invite-submit" disabled={busy} type="submit">
          <KeyRound size={16} /> {busy ? "Ativando..." : "Ativar conta"} <ChevronRight size={16} />
        </button>
        <p className="auth-hint muted"><LockKeyhole size={13} /> Você define a senha; nem o administrador tem acesso.</p>
      </motion.form>
    </div>
  );
}
