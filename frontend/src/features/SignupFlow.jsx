import { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { ArrowLeft, ArrowRight, Check, Mail, ShieldCheck } from "lucide-react";

import {
  PASSO_CODIGO,
  PASSO_DADOS,
  PASSO_PAGAMENTO,
  PASSO_PLANO,
  PASSO_SENHA,
  PASSOS,
  ROTULO_DO_PASSO,
  avaliarSenha,
  explicarErro,
  montarRetomada,
  validarCodigo,
  validarDados,
} from "./signupSteps";

/**
 * Funil publico: plano -> dados -> codigo -> senha -> pagamento.
 *
 * A conta nasce no passo da senha, ja bloqueada (PENDING_PAYMENT). Voltar do checkout
 * NAO libera nada: a tela apenas consulta o estado, e quem ativa e o webhook, depois de
 * conferir a assinatura na API do Mercado Pago.
 *
 * Nenhum preco sai daqui. O checkout envia apenas o codigo do plano.
 */

const brl = (v) => (typeof v === "number" ? v.toFixed(2).replace(".", ",") : "--");

function Trilha({ atual }) {
  const i = PASSOS.indexOf(atual);
  return (
    <ol className="signup-steps">
      {PASSOS.map((p, n) => (
        <li key={p} className={n < i ? "done" : n === i ? "current" : ""}>
          <span>{n < i ? <Check size={12} /> : n + 1}</span>
          {ROTULO_DO_PASSO[p]}
        </li>
      ))}
    </ol>
  );
}

function CartaoDoPlano({ plano, escolhido, onEscolher }) {
  return (
    <button
      type="button"
      className={`signup-plan${escolhido ? " selected" : ""}`}
      onClick={() => onEscolher(plano.code)}
      data-testid={`signup-plan-${plano.code}`}
    >
      <span className="signup-plan-head">
        <b>{plano.nome}</b>
        {plano.recomendado && <em className="plan-flag inline">Recomendado</em>}
      </span>
      <span className="signup-plan-price">
        R$ <b>{brl(plano.preco)}</b>
        <small>/mês</small>
      </span>
      <span className="signup-plan-audience">{plano.para_quem}</span>
    </button>
  );
}

export default function SignupFlow({ API, planoInicial, onEntrar, onCancelar, onAutenticar }) {
  const [passo, setPasso] = useState(planoInicial ? PASSO_DADOS : PASSO_PLANO);
  const [planos, setPlanos] = useState([]);
  const [plano, setPlano] = useState(planoInicial || "");
  const [dados, setDados] = useState({ name: "", email: "", acceptTerms: false });
  const [codigo, setCodigo] = useState("");
  const [senha, setSenha] = useState("");
  const [token, setToken] = useState("");
  const [erros, setErros] = useState({});
  const [erro, setErro] = useState("");
  const [aviso, setAviso] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [aberto, setAberto] = useState(true);
  // Trava sincrona: dois toques no mesmo tick nao podem disparar dois cadastros.
  const emVoo = useRef(false);

  // Enquanto PUBLIC_SIGNUP_ENABLED estiver desligada o funil responde 503. Perguntar
  // antes evita deixar a pessoa preencher nome, e-mail e termos para so entao descobrir
  // que o cadastro nem esta aberto.
  useEffect(() => {
    axios
      .get(`${API}/signup/config`)
      .then((r) => setAberto(r.data.enabled !== false))
      .catch((e) => console.error("[FORGE signup] config:", e));
  }, [API]);

  useEffect(() => {
    axios
      .get(`${API}/billing/plans`)
      .then((r) => setPlanos(r.data.plans || []))
      .catch((e) => {
        console.error("[FORGE signup] planos:", e);
        setErro("Não foi possível carregar os planos. Recarregue a página.");
      });
  }, [API]);

  const executar = useCallback(async (acao) => {
    if (emVoo.current) return null;
    emVoo.current = true;
    setOcupado(true);
    setErro("");
    try {
      return await acao();
    } catch (e) {
      console.error("[FORGE signup]", e?.response?.status, e?.response?.data ?? e);
      setErro(explicarErro(e));
      return null;
    } finally {
      emVoo.current = false;
      setOcupado(false);
    }
  }, []);

  const enviarDados = () =>
    executar(async () => {
      const v = validarDados(dados);
      setErros(v.erros);
      if (!v.ok) return null;
      await axios.post(`${API}/signup/start`, {
        name: dados.name.trim(),
        email: dados.email.trim().toLowerCase(),
        plan_code: plano,
        accept_terms: true,
      });
      setAviso("Enviamos um código de 6 dígitos para o seu e-mail.");
      setPasso(PASSO_CODIGO);
      return true;
    });

  const reenviar = () =>
    executar(async () => {
      await axios.post(`${API}/signup/start`, {
        name: dados.name.trim(),
        email: dados.email.trim().toLowerCase(),
        plan_code: plano,
        accept_terms: true,
      });
      setAviso("Código reenviado. Verifique também o spam.");
      return true;
    });

  const enviarCodigo = () =>
    executar(async () => {
      if (!validarCodigo(codigo)) {
        setErro("Digite os 6 dígitos do código.");
        return null;
      }
      const r = await axios.post(`${API}/signup/verify`, {
        email: dados.email.trim().toLowerCase(),
        code: codigo.trim(),
      });
      setToken(r.data.token);
      setAviso("");
      setPasso(PASSO_SENHA);
      return true;
    });

  const criarSenha = () =>
    executar(async () => {
      const f = avaliarSenha(senha, { email: dados.email });
      if (!f.ok) {
        setErro(`Sua senha precisa de ${f.problemas.join(", ")}.`);
        return null;
      }
      const r = await axios.post(`${API}/signup/create-password`, {
        token,
        password: senha,
      });
      // Ja entramos autenticados: se o pagamento for abandonado, a pessoa volta pelo
      // login normal e retoma de onde parou.
      onAutenticar?.(r.data.token, r.data.user);
      setPasso(PASSO_PAGAMENTO);
      return true;
    });

  const irParaPagamento = () =>
    executar(async () => {
      const r = await axios.post(`${API}/signup/checkout`, { token });
      window.location.href = r.data.checkout_url;
      return true;
    });

  const escolhido = planos.find((p) => p.code === plano);

  return (
    <div className="auth-shell signup">
      <div className="signup-card">
        <div className="signup-head">
          <div className="brand">
            <span className="brand-mark">F</span> FORGE
          </div>
          <button type="button" className="btn ghost small" onClick={onEntrar}>
            Já tenho conta
          </button>
        </div>

        <Trilha atual={passo} />

        {!aberto && (
          <p className="signup-closed" data-testid="signup-closed">
            O cadastro ainda não está aberto ao público. Se você já tem conta, entre pelo
            link acima; se recebeu um convite, use o link que enviamos.
          </p>
        )}

        {passo === PASSO_PLANO && (
          <>
            <h2>Escolha seu plano</h2>
            <p className="muted">Você pode trocar antes de pagar.</p>
            <div className="signup-plans">
              {planos.map((p) => (
                <CartaoDoPlano
                  key={p.code}
                  plano={p}
                  escolhido={p.code === plano}
                  onEscolher={setPlano}
                />
              ))}
            </div>
            <button
              type="button"
              className="btn primary"
              disabled={!plano || !aberto}
              onClick={() => setPasso(PASSO_DADOS)}
            >
              Continuar <ArrowRight size={16} />
            </button>
          </>
        )}

        {passo === PASSO_DADOS && (
          <>
            <h2>Seus dados</h2>
            {escolhido && (
              <p className="signup-chosen">
                Plano escolhido: <b>{escolhido.nome}</b> — R$ {brl(escolhido.preco)}/mês
                <button type="button" className="link" onClick={() => setPasso(PASSO_PLANO)}>
                  trocar
                </button>
              </p>
            )}
            <label>
              Nome
              <input
                value={dados.name}
                autoComplete="name"
                onChange={(e) => setDados({ ...dados, name: e.target.value })}
              />
            </label>
            {erros.name && <p className="form-error">{erros.name}</p>}

            <label>
              E-mail
              <input
                type="email"
                value={dados.email}
                autoComplete="email"
                inputMode="email"
                onChange={(e) => setDados({ ...dados, email: e.target.value })}
              />
            </label>
            {erros.email && <p className="form-error">{erros.email}</p>}

            <label className="checkbox">
              <input
                type="checkbox"
                checked={dados.acceptTerms}
                onChange={(e) => setDados({ ...dados, acceptTerms: e.target.checked })}
              />
              <span>
                Li e aceito os <a href="/termos">Termos de Uso</a> e a{" "}
                <a href="/privacidade">Política de Privacidade</a>.
              </span>
            </label>
            {erros.acceptTerms && <p className="form-error">{erros.acceptTerms}</p>}

            <div className="signup-nav">
              <button type="button" className="btn ghost" onClick={() => setPasso(PASSO_PLANO)}>
                <ArrowLeft size={16} /> Voltar
              </button>
              <button type="button" className="btn primary" disabled={ocupado || !aberto} onClick={enviarDados}>
                {ocupado ? "Enviando..." : "Continuar"}
              </button>
            </div>
          </>
        )}

        {passo === PASSO_CODIGO && (
          <>
            <h2>Confirme seu e-mail</h2>
            <p className="muted">
              <Mail size={14} /> Enviamos um código de 6 dígitos para{" "}
              <b>{dados.email}</b>. Ele vale por 15 minutos.
            </p>
            <input
              className="signup-code"
              value={codigo}
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              placeholder="000000"
              onChange={(e) => setCodigo(e.target.value.replace(/\D/g, ""))}
            />
            <div className="signup-nav">
              <button type="button" className="btn ghost" disabled={ocupado} onClick={reenviar}>
                Reenviar código
              </button>
              <button type="button" className="btn primary" disabled={ocupado} onClick={enviarCodigo}>
                {ocupado ? "Conferindo..." : "Confirmar"}
              </button>
            </div>
          </>
        )}

        {passo === PASSO_SENHA && (
          <>
            <h2>Crie sua senha</h2>
            <p className="muted">Mínimo de 8 caracteres, com letras e números.</p>
            <label>
              Senha
              <input
                type="password"
                value={senha}
                autoComplete="new-password"
                onChange={(e) => setSenha(e.target.value)}
              />
            </label>
            <button type="button" className="btn primary" disabled={ocupado} onClick={criarSenha}>
              {ocupado ? "Criando conta..." : "Criar conta"}
            </button>
          </>
        )}

        {passo === PASSO_PAGAMENTO && (
          <>
            <h2>Falta o pagamento</h2>
            <p className="muted">
              Sua conta foi criada. O acesso é liberado assim que a assinatura for
              confirmada pelo Mercado Pago.
            </p>
            {escolhido && (
              <p className="signup-chosen">
                <b>{escolhido.nome}</b> — R$ {brl(escolhido.preco)}/mês
              </p>
            )}
            <button type="button" className="btn primary" disabled={ocupado} onClick={irParaPagamento}>
              {ocupado ? "Abrindo pagamento..." : "Ir para o pagamento"}
            </button>
            <p className="plan-footnote">
              <ShieldCheck size={14} /> Pagamento pelo Mercado Pago. O FORGE não armazena
              dados do seu cartão.
            </p>
          </>
        )}

        {aviso && <p className="form-note">{aviso}</p>}
        {erro && <p className="form-error">{erro}</p>}

        <button type="button" className="link quiet" onClick={onCancelar}>
          Voltar para a página inicial
        </button>
      </div>
    </div>
  );
}

/**
 * Tela de quem entrou mas ainda nao pagou (item 9 do escopo).
 *
 * Mostra o plano escolhido, as alternativas e o botao de continuar. Nao mostra nada do
 * aplicativo — e o backend, nao esta tela, que garante isso.
 */
export function PagamentoPendente({ API, user, onSair, retornando, onLiberado }) {
  const [planos, setPlanos] = useState([]);
  const [escolhido, setEscolhido] = useState(user?.plan_code_escolhido || "");
  const [erro, setErro] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [conferindo, setConferindo] = useState(Boolean(retornando));
  const emVoo = useRef(false);

  // Volta do checkout: a tela NAO ativa nada, so pergunta ao servidor de tempos em
  // tempos se o webhook ja chegou. Enquanto nao chegar, a conta segue sem acesso.
  useEffect(() => {
    if (!retornando) return undefined;
    let vivo = true;
    let tentativas = 0;
    const timer = setInterval(async () => {
      tentativas += 1;
      try {
        const r = await axios.get(`${API}/billing/me`);
        if (vivo && r.data.status === "active") {
          clearInterval(timer);
          setConferindo(false);
          onLiberado?.();
          return;
        }
      } catch (e) {
        console.error("[FORGE pendente] consulta:", e);
      }
      // Depois de ~2 minutos paramos de perguntar: pode ter falhado o pagamento, e
      // ficar girando para sempre daria a impressao de que algo esta em andamento.
      if (vivo && tentativas >= 30) {
        clearInterval(timer);
        setConferindo(false);
      }
    }, 4000);
    return () => {
      vivo = false;
      clearInterval(timer);
    };
  }, [API, retornando, onLiberado]);

  useEffect(() => {
    axios
      .get(`${API}/billing/plans`)
      .then((r) => setPlanos(r.data.plans || []))
      .catch((e) => {
        console.error("[FORGE pendente] planos:", e);
        setErro("Não foi possível carregar os planos. Recarregue a página.");
      });
  }, [API]);

  const pagar = async (code) => {
    if (emVoo.current) return;
    emVoo.current = true;
    setOcupado(true);
    setErro("");
    try {
      const r = await axios.post(`${API}/billing/checkout`, { plan_code: code });
      window.location.href = r.data.checkout_url;
    } catch (e) {
      console.error("[FORGE pendente] checkout:", e?.response?.status, e?.response?.data ?? e);
      setErro(explicarErro(e));
    } finally {
      emVoo.current = false;
      setOcupado(false);
    }
  };

  const { escolhido: destaque, alternativas } = montarRetomada(planos, escolhido);

  return (
    <div className="auth-shell signup">
      <div className="signup-card wide">
        <div className="signup-head">
          <div className="brand">
            <span className="brand-mark">F</span> FORGE
          </div>
          <button type="button" className="btn ghost small" onClick={onSair}>
            Sair
          </button>
        </div>

        <h2>{conferindo ? "Confirmando sua assinatura" : "Continue seu pagamento"}</h2>
        <p className="muted">
          {conferindo
            ? "Estamos confirmando o pagamento com o Mercado Pago. Isso costuma levar alguns segundos."
            : `Sua conta está criada, ${user?.name?.split(" ")[0] || "atleta"}. O acesso abre assim que a assinatura for confirmada.`}
        </p>

        {destaque && (
          <section className="plan-card recommended" data-testid="pending-chosen">
            <span className="plan-flag">Seu plano</span>
            <p className="eyebrow">{destaque.nome}</p>
            <p className="plan-price">
              <span className="plan-currency">R$</span>
              <b>{brl(destaque.preco)}</b>
              <small>/mês</small>
            </p>
            <p className="plan-audience">{destaque.para_quem}</p>
            <button
              type="button"
              className="btn primary plan-cta"
              disabled={ocupado}
              onClick={() => pagar(destaque.code)}
            >
              {ocupado ? "Abrindo..." : "Continuar pagamento"} <ArrowRight size={16} />
            </button>
          </section>
        )}

        {alternativas.length > 0 && (
          <>
            <p className="eyebrow spaced">Ou troque de plano</p>
            <div className="signup-plans">
              {alternativas.map((p) => (
                <CartaoDoPlano key={p.code} plano={p} escolhido={false} onEscolher={setEscolhido} />
              ))}
            </div>
          </>
        )}

        {erro && <p className="form-error">{erro}</p>}
      </div>
    </div>
  );
}
