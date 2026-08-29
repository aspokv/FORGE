import { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { motion } from "framer-motion";
import { ArrowLeft, Check, KeyRound, Mail, ShieldCheck } from "lucide-react";

import { API, useAuth } from "./AuthContext";
import {
  PASSO_ENVIADO,
  PASSO_LINK_INVALIDO,
  PASSO_NOVA_SENHA,
  PASSO_PEDIR,
  PASSO_PRONTO,
  emailParece,
  explicarErro,
  passoInicial,
  problemaDaSenha,
  senhasConferem,
  tokenDaRota,
} from "./passwordResetRules";
// O modulo de regras se chama passwordResetRules, e nao passwordReset, porque o Windows
// nao distingue maiusculas em nome de arquivo: "./passwordReset" resolvia para o modulo
// de regras em vez deste componente, e o build quebrava com "does not contain a default
// export" — um erro que nao aparece em Linux e apareceria so no CI.

/**
 * Recuperacao de senha: pedir, confirmar envio, criar a nova, sucesso e erro.
 *
 * A tela nunca diz se a conta existe. O servidor responde igual nos dois casos, e repetir
 * essa resposta sem interpretar e o que mantem a promessa: qualquer "não encontramos esse
 * e-mail" aqui recriaria o oraculo que o backend evita.
 */

export default function PasswordReset() {
  const { navigate, route } = useAuth();
  const [passo, setPasso] = useState(() => passoInicial(route));
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [confirmacao, setConfirmacao] = useState("");
  const [erro, setErro] = useState("");
  const [aviso, setAviso] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const emVoo = useRef(false);

  const token = tokenDaRota(route);

  // Confere o link antes de mostrar o formulario: pedir uma senha nova para depois dizer
  // que o link expirou seria trabalho jogado fora.
  useEffect(() => {
    if (!token) return;
    let vivo = true;
    axios
      .get(`${API}/auth/reset-password/${encodeURIComponent(token)}`)
      .catch((e) => {
        if (!vivo) return;
        console.error("[FORGE reset] link inválido:", e?.response?.status);
        setPasso(PASSO_LINK_INVALIDO);
      });
    return () => {
      vivo = false;
    };
  }, [token]);

  const executar = useCallback(async (acao) => {
    if (emVoo.current) return;
    emVoo.current = true;
    setOcupado(true);
    setErro("");
    try {
      await acao();
    } catch (e) {
      console.error("[FORGE reset]", e?.response?.status, e?.response?.data ?? e);
      setErro(explicarErro(e));
    } finally {
      emVoo.current = false;
      setOcupado(false);
    }
  }, []);

  const pedir = () =>
    executar(async () => {
      if (!emailParece(email)) {
        setErro("Digite um e-mail válido.");
        return;
      }
      const r = await axios.post(`${API}/auth/forgot-password`, {
        email: email.trim().toLowerCase(),
      });
      // A mensagem vem do servidor e e a mesma para qualquer e-mail.
      setAviso(r.data?.message || "");
      setPasso(PASSO_ENVIADO);
    });

  const trocar = () =>
    executar(async () => {
      const problema = problemaDaSenha(senha, email);
      if (problema) {
        setErro(problema);
        return;
      }
      if (!senhasConferem(senha, confirmacao)) {
        setErro("As senhas não são iguais.");
        return;
      }
      await axios.post(`${API}/auth/reset-password`, { token, password: senha });
      setPasso(PASSO_PRONTO);
    });

  const irParaLogin = () => navigate("/login");

  return (
    <div className="auth-shell" data-testid="password-reset">
      <div className="auth-brand">
        <span className="brand-mark">F</span>
        <span>FORGE</span>
        <small>ADVANCED TRAINING OS</small>
      </div>

      <motion.div
        className="auth-card"
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
      >
        {passo === PASSO_PEDIR && (
          <>
            <p className="eyebrow">RECUPERAR ACESSO</p>
            <h1>Esqueceu a senha?</h1>
            <p className="muted">
              Informe seu e-mail e enviaremos um link para criar uma nova senha.
            </p>
            <label className="deep-field">
              <span>E-mail</span>
              <input
                data-testid="reset-email"
                type="email"
                autoComplete="email"
                inputMode="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
            {erro && <div className="auth-error" data-testid="reset-error">{erro}</div>}
            <button
              type="button"
              className="primary-button auth-submit"
              data-testid="reset-submit"
              disabled={ocupado}
              onClick={pedir}
            >
              <Mail size={16} /> {ocupado ? "Enviando..." : "Enviar link"}
            </button>
            <button type="button" className="text-button" onClick={irParaLogin}>
              <ArrowLeft size={14} /> Voltar para o login
            </button>
          </>
        )}

        {passo === PASSO_ENVIADO && (
          <>
            <p className="eyebrow">VERIFIQUE SEU E-MAIL</p>
            <h1>Link enviado.</h1>
            <p className="muted" data-testid="reset-neutral">{aviso}</p>
            <p className="auth-hint muted">
              <ShieldCheck size={13} /> O link vale por 30 minutos e só pode ser usado uma vez.
            </p>
            <button type="button" className="primary-button auth-submit" onClick={irParaLogin}>
              Voltar para o login
            </button>
            <button
              type="button"
              className="text-button"
              disabled={ocupado}
              onClick={() => setPasso(PASSO_PEDIR)}
            >
              Usar outro e-mail
            </button>
          </>
        )}

        {passo === PASSO_NOVA_SENHA && (
          <>
            <p className="eyebrow">NOVA SENHA</p>
            <h1>Crie sua nova senha.</h1>
            <p className="muted">
              Mínimo de 8 caracteres, com letras e números. Ao trocar, as sessões abertas
              em outros dispositivos serão encerradas.
            </p>
            <label className="deep-field">
              <span>Nova senha</span>
              <input
                data-testid="reset-new-password"
                type="password"
                autoComplete="new-password"
                value={senha}
                onChange={(e) => setSenha(e.target.value)}
              />
            </label>
            <label className="deep-field">
              <span>Confirme a nova senha</span>
              <input
                data-testid="reset-confirm-password"
                type="password"
                autoComplete="new-password"
                value={confirmacao}
                onChange={(e) => setConfirmacao(e.target.value)}
              />
            </label>
            {erro && <div className="auth-error" data-testid="reset-error">{erro}</div>}
            <button
              type="button"
              className="primary-button auth-submit"
              data-testid="reset-confirm"
              disabled={ocupado}
              onClick={trocar}
            >
              <KeyRound size={16} /> {ocupado ? "Alterando..." : "Alterar senha"}
            </button>
          </>
        )}

        {passo === PASSO_PRONTO && (
          <>
            <p className="eyebrow">TUDO CERTO</p>
            <h1>Senha alterada.</h1>
            <p className="muted" data-testid="reset-success">
              Sua senha foi alterada e as sessões anteriores foram encerradas. Entre com a
              nova senha.
            </p>
            <button
              type="button"
              className="primary-button auth-submit"
              data-testid="reset-go-login"
              onClick={irParaLogin}
            >
              <Check size={16} /> Ir para o login
            </button>
          </>
        )}

        {passo === PASSO_LINK_INVALIDO && (
          <>
            <p className="eyebrow">LINK INVÁLIDO</p>
            <h1>Este link não vale mais.</h1>
            <p className="muted" data-testid="reset-invalid">
              Ele expirou ou já foi usado. Peça um novo para continuar.
            </p>
            <button
              type="button"
              className="primary-button auth-submit"
              onClick={() => {
                setErro("");
                setPasso(PASSO_PEDIR);
                navigate("/recuperar");
              }}
            >
              Pedir um novo link
            </button>
            <button type="button" className="text-button" onClick={irParaLogin}>
              <ArrowLeft size={14} /> Voltar para o login
            </button>
          </>
        )}
      </motion.div>
    </div>
  );
}
