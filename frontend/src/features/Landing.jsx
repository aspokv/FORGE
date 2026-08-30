import { useEffect, useState } from "react";
import axios from "axios";
import {
  ArrowDown,
  ArrowRight,
  Check,
  Dumbbell,
  LineChart,
  ShieldCheck,
  Sparkles,
  Utensils,
} from "lucide-react";

/**
 * Pagina publica do FORGE: o unico endereco que o proprietario precisa divulgar.
 *
 * Abre sem login. O catalogo vem de /api/billing/plans, que e publico e ja devolve nome,
 * preco, publico e recursos — a tela nao escreve preco nenhum, para nao existir um
 * segundo lugar onde o valor possa divergir do que e cobrado.
 */

const brl = (v) => (typeof v === "number" ? v.toFixed(2).replace(".", ",") : "--");

const BENEFICIOS = [
  {
    icone: Dumbbell,
    titulo: "Treino que se ajusta a você",
    texto:
      "Divisão, volume e progressão montados a partir da sua avaliação, do seu tempo " +
      "disponível e das regiões que você quer priorizar.",
  },
  {
    icone: Utensils,
    titulo: "Alimentação no mesmo plano",
    texto:
      "Metas calculadas para o seu objetivo, com substituições equivalentes para quando " +
      "faltar um alimento — sem recomeçar o plano do zero.",
  },
  {
    icone: LineChart,
    titulo: "Progressão registrada",
    texto:
      "Cada série fica no histórico e alimenta a carga da próxima sessão. Você vê a " +
      "evolução em vez de tentar lembrar dela.",
  },
];

function Plano({ plano, onComecar }) {
  return (
    <section
      className={`plan-card${plano.recomendado ? " recommended" : ""}`}
      data-testid={`landing-plan-${plano.code}`}
    >
      {plano.recomendado && <span className="plan-flag">Recomendado</span>}

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
          <li key={r}>
            <Check size={14} /> {r}
          </li>
        ))}
      </ul>

      {plano.em_breve && plano.em_breve.length > 0 && (
        <div className="plan-soon">
          <p className="eyebrow">Em breve</p>
          <ul className="plan-features soon">
            {plano.em_breve.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      <button
        type="button"
        className="btn primary plan-cta"
        onClick={() => onComecar(plano.code)}
        data-testid={`landing-plan-cta-${plano.code}`}
      >
        Escolher {plano.nome.replace("FORGE ", "")} <ArrowRight size={16} />
      </button>
    </section>
  );
}

export default function Landing({ API, onComecar, onEntrar }) {
  const [planos, setPlanos] = useState([]);
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    let vivo = true;
    axios
      .get(`${API}/billing/plans`)
      .then((r) => {
        if (!vivo) return;
        setPlanos(r.data.plans || []);
      })
      .catch((e) => {
        if (!vivo) return;
        // Sem catalogo nao ha o que oferecer: melhor dizer isso do que mostrar uma
        // pagina vazia que parece quebrada.
        console.error("[FORGE landing] não foi possível carregar os planos:", e);
        setErro("Não foi possível carregar os planos agora. Recarregue a página.");
      })
      .finally(() => vivo && setCarregando(false));
    return () => {
      vivo = false;
    };
  }, [API]);

  return (
    <div className="landing">
      <header className="landing-top">
        <div className="brand">
          <span className="brand-mark">F</span> FORGE
        </div>
        <nav className="landing-nav" aria-label="Navegação principal">
          <a href="#metodo">O método</a>
          <a href="#planos">Planos</a>
        </nav>
        <button
          type="button"
          className="btn ghost landing-login"
          onClick={onEntrar}
          data-testid="landing-login"
        >
          Já tenho conta <ArrowRight size={15} />
        </button>
      </header>

      <section className="landing-hero">
        <div className="landing-hero-copy">
          <p className="eyebrow landing-kicker"><span /> Sistema de performance individual</p>
          <h1>
            Evolução não é<br />
            <em>acidente.</em>
          </h1>
          <p className="landing-lead">
            Treino e alimentação construídos em torno do seu corpo, da sua rotina e do
            seu histórico. O FORGE transforma cada sessão em uma decisão melhor para a
            próxima.
          </p>
          <div className="landing-actions">
            <button
              type="button"
              className="btn primary"
              onClick={() => onComecar(planos.find((p) => p.recomendado)?.code || "pro")}
              data-testid="landing-primary-cta"
            >
              Construir meu plano <ArrowRight size={16} />
            </button>
            <a className="landing-text-link" href="#metodo">
              Conhecer o método <ArrowDown size={14} />
            </a>
          </div>
          <div className="landing-proof" aria-label="Diferenciais do FORGE">
            <span><b>01</b> Avaliação individual</span>
            <span><b>02</b> Progressão contínua</span>
            <span><b>03</b> Treino + nutrição</span>
          </div>
        </div>

        <div className="landing-instrument" aria-label="Exemplo da inteligência do FORGE">
          <div className="instrument-top">
            <span className="eyebrow">FORGE / SESSÃO 04</span>
            <span className="instrument-live"><i /> Plano em evolução</span>
          </div>
          <div className="instrument-command">
            <span>PRÓXIMA DECISÃO</span>
            <h2>Supino inclinado</h2>
            <p>Seu histórico indica progressão de carga hoje.</p>
          </div>
          <div className="instrument-metrics">
            <div><span>Carga alvo</span><strong>32<small>kg</small></strong></div>
            <div><span>Repetições</span><strong>8–10</strong></div>
            <div><span>Intensidade</span><strong>RIR 2</strong></div>
          </div>
          <div className="instrument-progress">
            <div><span>Progressão do ciclo</span><b>76%</b></div>
            <i><b /></i>
          </div>
          <p className="instrument-note"><Sparkles size={14} /> Ajustado a partir das últimas 6 sessões</p>
        </div>
      </section>

      <section className="landing-manifesto" id="metodo">
        <p className="eyebrow">O método</p>
        <p className="manifesto-copy">
          Seu corpo muda. Sua rotina muda. Seu plano precisa acompanhar.
          <span> O FORGE observa, registra e recalibra.</span>
        </p>
      </section>

      <section className="landing-section landing-section-numbered">
        <div className="section-heading">
          <div><p className="eyebrow">01 / Para quem é</p><h2>Precisão para cada fase.</h2></div>
          <p>Uma estrutura clara para começar — profundidade suficiente para continuar evoluindo.</p>
        </div>
        <div className="landing-audience">
          <article>
            <span className="audience-number">01</span>
            <h3>Está começando</h3>
            <p>
              Você recebe uma divisão pronta, com carga inicial e técnica descrita, em vez
              de copiar a ficha de outra pessoa.
            </p>
          </article>
          <article>
            <span className="audience-number">02</span>
            <h3>Já treina há anos</h3>
            <p>
              Prioriza as regiões que quer desenvolver, controla intensidade e usa
              protocolos avançados quando faz sentido.
            </p>
          </article>
          <article>
            <span className="audience-number">03</span>
            <h3>Quer treino e dieta juntos</h3>
            <p>
              Ganho de massa, emagrecimento ou recomposição com metas coerentes entre o
              que você treina e o que você come.
            </p>
          </article>
        </div>
      </section>

      <section className="landing-section landing-benefit-section">
        <div className="section-heading">
          <div><p className="eyebrow">02 / O sistema</p><h2>Uma inteligência. Três pilares.</h2></div>
          <p>Cada escolha conversa com a próxima. Nada é montado de forma isolada.</p>
        </div>
        <div className="landing-benefits">
          {BENEFICIOS.map(({ icone: Icone, titulo, texto }, index) => (
            <article key={titulo}>
              <div className="benefit-icon"><Icone size={20} /></div>
              <span className="benefit-index">0{index + 1}</span>
              <h3>{titulo}</h3>
              <p>{texto}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-section" id="planos">
        <div className="section-heading plans-heading">
          <div><p className="eyebrow">03 / Planos</p><h2>Escolha o seu nível de precisão.</h2></div>
          <p>Comece no plano certo para o seu momento. Evolua quando estiver pronto.</p>
        </div>

        {carregando && <p className="muted">Carregando planos...</p>}
        {erro && <p className="form-error">{erro}</p>}

        <div className="plan-grid landing-plan-grid">
          {planos.map((p) => (
            <Plano key={p.code} plano={p} onComecar={onComecar} />
          ))}
        </div>

        <p className="plan-footnote">
          <ShieldCheck size={14} /> Pagamento processado pelo Mercado Pago. O FORGE não
          armazena dados do seu cartão.
        </p>
      </section>

      <footer className="landing-footer">
        <div className="brand"><span className="brand-mark">F</span> FORGE</div>
        <p>Seu treino deixa de ser um palpite.</p>
        <button type="button" className="btn ghost" onClick={onEntrar} data-testid="landing-footer-login">Entrar</button>
      </footer>
    </div>
  );
}
