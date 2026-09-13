import { useEffect, useState } from "react";
import axios from "axios";
import { motion } from "framer-motion";
import { ChevronRight, Eye, EyeOff, KeyRound, LockKeyhole, Mail } from "lucide-react";
import forgeWordmark from "../assets/forge-wordmark-transparent.svg";
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
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const submit = async e => {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      const { data } = await axios.post(API + "/auth/login", { email: email.trim().toLowerCase(), password });
      signIn(data.token, data.user);
      navigate(data.user.role === "SUPER_ADMIN" ? "/admin" : "/app", true);
    } catch (e) {
      setErr(formatError(e.response?.data?.detail));
    } finally { setBusy(false); }
  };

  return (
    <div className="auth-shell login-shell" data-testid="login-screen">
      <main className="login-frame">
        <header className="login-brand" aria-label="FORGE">
          <img src={forgeWordmark} alt="FORGE" />
          <span>ADVANCED TRAINING OS</span>
        </header>

        <section className="login-intro" aria-labelledby="login-title">
          <p className="login-kicker">ACESSO AO SEU SISTEMA</p>
          <h1 id="login-title">
            SEU PROGRAMA.
            <span>SUA EVOLUÇÃO.</span>
          </h1>
          <p>Seu próximo nível começa aqui.</p>
        </section>

        <motion.form
          className="auth-card login-card"
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.28, ease: "easeOut" }}
          onSubmit={submit}
          aria-busy={busy}
        >
          <div className="login-card-heading">
            <p className="eyebrow">ACESSO FORGE</p>
            <h2>Entre para continuar seu plano.</h2>
          </div>

          <div className="deep-field login-field">
            <label htmlFor="login-email">E-mail</label>
            <span className="login-input">
              <Mail size={17} aria-hidden="true" />
              <input
                id="login-email"
                data-testid="login-email"
                type="email"
                inputMode="email"
                autoComplete="email"
                placeholder="seu@email.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
              />
            </span>
          </div>

          <div className="deep-field login-field">
            <label htmlFor="login-password">Senha</label>
            <span className="login-input">
              <LockKeyhole size={17} aria-hidden="true" />
              <input
                id="login-password"
                data-testid="login-password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                placeholder="Sua senha"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
              />
              <button
                type="button"
                className="login-password-toggle"
                data-testid="login-password-toggle"
                aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}
                aria-pressed={showPassword}
                onClick={() => setShowPassword(current => !current)}
              >
                {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
              </button>
            </span>
          </div>

          <button
            type="button"
            className="login-forgot"
            data-testid="forgot-password-link"
            onClick={() => navigate("/recuperar")}
          >
            Esqueci minha senha
          </button>

          {err && <div className="auth-error" role="alert" data-testid="login-error">{err}</div>}

          <button
            className="primary-button auth-submit login-primary"
            data-testid="login-submit"
            disabled={busy}
            type="submit"
          >
            <span>{busy ? "ENTRANDO..." : "ENTRAR"}</span>
            <ChevronRight size={18} aria-hidden="true" />
          </button>

          <div className="login-signup">
            <p>Ainda não tem uma conta?</p>
            <button
              type="button"
              className="login-register"
              data-testid="login-register-link"
              onClick={() => navigate("/assinar")}
            >
              CRIAR CONTA
              <ChevronRight size={17} aria-hidden="true" />
            </button>
          </div>
        </motion.form>
      </main>
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
