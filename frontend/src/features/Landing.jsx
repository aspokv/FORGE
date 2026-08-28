import { useEffect, useState } from "react";
import axios from "axios";
import { ArrowRight, Check, Dumbbell, LineChart, ShieldCheck, Utensils } from "lucide-react";

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
      >
        Começar agora <ArrowRight size={16} />
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
        <button type="button" className="btn ghost" onClick={onEntrar}>
          Já tenho conta — Entrar
        </button>
      </header>

      <section className="landing-hero">
        <p className="eyebrow">Treino e nutrição em um só lugar</p>
        <h1>
          Seu treino deixa de ser
          <br />
          um palpite.
        </h1>
        <p className="landing-lead">
          O FORGE monta treino e alimentação a partir da sua avaliação, acompanha cada
          série registrada e ajusta a progressão sozinho. Você escolhe o plano, faz a
          avaliação e começa no mesmo dia.
        </p>
        <div className="landing-actions">
          <button
            type="button"
            className="btn primary"
            onClick={() => onComecar(planos.find((p) => p.recomendado)?.code || "pro")}
          >
            Começar agora <ArrowRight size={16} />
          </button>
          <button type="button" className="btn ghost" onClick={onEntrar}>
            Já tenho conta
          </button>
        </div>
      </section>

      <section className="landing-section">
        <p className="eyebrow">Para quem é</p>
        <h2>Feito para quem treina com objetivo</h2>
        <div className="landing-audience">
          <article>
            <h3>Está começando</h3>
            <p>
              Você recebe uma divisão pronta, com carga inicial e técnica descrita, em vez
              de copiar a ficha de outra pessoa.
            </p>
          </article>
          <article>
            <h3>Já treina há anos</h3>
            <p>
              Prioriza as regiões que quer desenvolver, controla intensidade e usa
              protocolos avançados quando faz sentido.
            </p>
          </article>
          <article>
            <h3>Quer treino e dieta juntos</h3>
            <p>
              Ganho de massa, emagrecimento ou recomposição com metas coerentes entre o
              que você treina e o que você come.
            </p>
          </article>
        </div>
      </section>

      <section className="landing-section">
        <p className="eyebrow">Benefícios</p>
        <h2>O que você recebe</h2>
        <div className="landing-benefits">
          {BENEFICIOS.map(({ icone: Icone, titulo, texto }) => (
            <article key={titulo}>
              <Icone size={20} />
              <h3>{titulo}</h3>
              <p>{texto}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-section" id="planos">
        <p className="eyebrow">Planos</p>
        <h2>Escolha como quer começar</h2>
        <p className="landing-lead small">
          Assinatura mensal. Você escolhe o plano antes de criar a conta e pode trocar
          antes de pagar.
        </p>

        {carregando && <p className="muted">Carregando planos...</p>}
        {erro && <p className="form-error">{erro}</p>}

        <div className="plan-grid">
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
        <span>FORGE</span>
        <button type="button" className="btn ghost" onClick={onEntrar}>
          Entrar
        </button>
      </footer>
    </div>
  );
}
