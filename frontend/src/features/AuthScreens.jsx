import { useEffect, useState } from "react";
import axios from "axios";
import { motion } from "framer-motion";
import { ArrowRight, ChevronRight, Eye, EyeOff, KeyRound, Mail, LockKeyhole } from "lucide-react";
import "./login-forge.css";
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
  const [verSenha, setVerSenha] = useState(false);
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
    <div className="forge-login" data-testid="login-screen">
      {/*
        * O letreiro FORGE e a regua nao sao interface: sao placa iluminada na parede, dentro
        * da foto. Desenhar um wordmark em HTML por cima duplicaria a marca.
        */}
      <header className="forge-login-hero">
        <h1 className="forge-login-titulo">
          <span>Seu programa.</span>
          <em>Sua evolução.</em>
        </h1>
        <p className="forge-login-subtitulo">Seu próximo nível começa aqui.</p>
      </header>

      <motion.form className="forge-login-card" initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} onSubmit={submit}>
        <p className="forge-login-chamada">Entre para continuar seu plano.</p>

        {/* O rotulo fica sempre encaixado na borda, e nao flutuando ao foco: a moldura da
            tela precisa ser a mesma com o campo vazio e com o campo preenchido. */}
        <div className="forge-campo">
          <input id="forge-login-email" data-testid="login-email" type="email" autoComplete="email"
                 value={email} onChange={e => setEmail(e.target.value)} required />
          <label htmlFor="forge-login-email">E-mail</label>
          <Mail className="forge-campo-icone" size={20} aria-hidden="true" />
        </div>

        <div className="forge-campo">
          <input id="forge-login-senha" data-testid="login-password" type={verSenha ? "text" : "password"}
                 autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required />
          <label htmlFor="forge-login-senha">Senha</label>
          <button type="button" className="forge-campo-olho" data-testid="login-toggle-password"
                  aria-pressed={verSenha} aria-label={verSenha ? "Ocultar senha" : "Mostrar senha"}
                  onClick={() => setVerSenha(v => !v)}>
            {verSenha ? <Eye size={20} aria-hidden="true" /> : <EyeOff size={20} aria-hidden="true" />}
          </button>
        </div>

        <button type="button" className="forge-login-esqueci" data-testid="forgot-password-link" onClick={() => navigate("/recuperar")}>
          Esqueci minha senha
        </button>

        {err && <div className="forge-login-erro" data-testid="login-error" role="alert">{err}</div>}

        <button className="forge-login-entrar" data-testid="login-submit" disabled={busy} type="submit">
          <span>{busy ? "Entrando…" : "Entrar"}</span>
          <ArrowRight size={20} aria-hidden="true" />
        </button>

        <hr className="forge-login-divisor" />
        <p className="forge-login-conta">Ainda não tem uma conta?</p>
        <button type="button" className="forge-login-criar" data-testid="login-signup-link" onClick={() => navigate("/assinar")}>
          Criar conta
        </button>
      </motion.form>

      <footer className="forge-login-rodape">
        <p>Mais disciplina</p>
        <p>Mais você</p>
        <span className="forge-login-regua" aria-hidden="true" />
      </footer>
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
