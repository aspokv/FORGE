import { useEffect, useState } from "react";
import axios from "axios";
import { ArrowRight, Check, ShieldCheck } from "lucide-react";
import LandingProductPreview from "./LandingProductPreview";
import LandingStorytelling from "./LandingStorytelling";
import "./landing-premium.css";

/**
 * Pagina publica do FORGE: o unico endereco que o proprietario precisa divulgar.
 *
 * Abre sem login. O catalogo vem de /api/billing/plans, que e publico e ja devolve nome,
 * preco, publico e recursos — a tela nao escreve preco nenhum, para nao existir um
 * segundo lugar onde o valor possa divergir do que e cobrado.
 *
 * Nada aqui inventa numero. Onde antes havia uma maquete da Home remontada em marcacao,
 * com calorias e cargas ilustrativas, agora ha captura real do produto.
 */

const brl = (v) => (typeof v === "number" ? v.toFixed(2).replace(".", ",") : "--");

/**
 * "FORGE ESSENCIAL" -> "Essencial".
 *
 * O catalogo devolve o nome em caixa alta, e o botao pedido e "Assinar Essencial".
 * Caixa alta dentro de uma frase gritaria; a normalizacao fica aqui e nao no back, porque
 * e decisao de apresentacao — o nome oficial do plano continua sendo o que a API diz.
 */
export const nomeCurto = (nome) =>
  String(nome || "")
    .replace(/^FORGE\s+/i, "")
    .toLocaleLowerCase("pt-BR")
    .replace(/(^|\s)(\p{L})/gu, (_, antes, letra) => antes + letra.toLocaleUpperCase("pt-BR"));

const PASSOS = [
  {
    n: "01",
    titulo: "Você responde uma avaliação curta",
    texto:
      "Objetivo, experiência, quantos dias tem por semana e quais regiões quer " +
      "priorizar. Leva poucos minutos.",
  },
  {
    n: "02",
    titulo: "O FORGE monta sua semana",
    texto:
      "Divisão, exercícios, séries e cargas iniciais — prontos, com a técnica descrita " +
      "em cada movimento.",
  },
  {
    n: "03",
    titulo: "Cada treino ajusta o próximo",
    texto:
      "Você registra o que fez. O plano usa isso para subir carga, trocar exercício e " +
      "manter a progressão no seu ritmo.",
  },
];

function Plano({ plano, onComecar }) {
  const curto = nomeCurto(plano.nome);
  return (
    <article
      className={`lp-plano${plano.recomendado ? " recomendado" : ""}`}
      data-testid={`landing-plan-${plano.code}`}
    >
      {plano.recomendado && <span className="lp-plano-flag">Recomendado</span>}

      <p className="lp-eyebrow">{plano.nome}</p>
      <p className="lp-plano-preco">
        <span>R$</span>
        <b>{brl(plano.preco)}</b>
        <small>/mês</small>
      </p>
      {plano.cobranca && <p className="lp-plano-cobranca">{plano.cobranca}</p>}

      <p className="lp-plano-publico">{plano.para_quem}</p>

      <ul className="lp-plano-recursos">
        {plano.recursos.map((r) => (
          <li key={r}>
            <Check size={14} aria-hidden="true" /> {r}
          </li>
        ))}
      </ul>

      {plano.em_breve && plano.em_breve.length > 0 && (
        <div className="lp-plano-embreve">
          <p className="lp-eyebrow">Em breve</p>
          <ul>
            {plano.em_breve.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      <button
        type="button"
        className={`lp-btn${plano.recomendado ? " lp-btn-primario" : ""}`}
        onClick={() => onComecar(plano.code)}
        data-testid={`landing-plan-cta-${plano.code}`}
        id={`landing-assinar-${plano.code}`}
        name={`assinar-${plano.code}`}
      >
        Assinar {curto} <ArrowRight size={16} aria-hidden="true" />
      </button>
    </article>
  );
}

export default function Landing({ API, onComecar, onEntrar }) {
  const [planos, setPlanos] = useState([]);
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(true);

  // Ver o comentario de `body.lp-ativa` em landing-premium.css: sem isto o painel preso
  // do storytelling nao gruda no celular. Sai do body assim que a landing desmonta.
  useEffect(() => {
    document.body.classList.add("lp-ativa");
    return () => document.body.classList.remove("lp-ativa");
  }, []);

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
        console.error("[FORGE landing] nao foi possivel carregar os planos:", e);
        setErro("Não foi possível carregar os planos agora. Recarregue a página.");
      })
      .finally(() => vivo && setCarregando(false));
    return () => {
      vivo = false;
    };
  }, [API]);

  return (
    <div className="landing-premium">
      <header className="lp-topo">
        <div className="lp-marca">
          <span className="lp-marca-selo">F</span> FORGE
        </div>
        <nav className="lp-nav" aria-label="Navegação principal">
          <a href="#por-dentro">Por dentro</a>
          <a href="#metodo">O método</a>
          <a href="#planos">Planos</a>
        </nav>
        <button
          type="button"
          className="lp-btn lp-btn-fantasma lp-topo-entrar"
          onClick={onEntrar}
          data-testid="landing-login"
          id="landing-ja-tenho-conta-topo"
          name="ja-tenho-conta"
        >
          Já tenho conta <ArrowRight size={15} aria-hidden="true" />
        </button>
      </header>

      {/*
        O hero e curto de proposito: titulo, linha tecnica, os dois botoes e a composicao
        logo abaixo deles. A composicao continua para a proxima dobra em vez de caber
        inteira — e o que convida a rolar.
      */}
      <section className="lp-hero">
        <p className="lp-hero-kicker">Sistema de performance individual</p>
        <h1>
          Seu próximo nível
          <br />
          <em>começa aqui.</em>
        </h1>
        <p className="lp-hero-lead">
          Treino, nutrição e evolução. Um sistema construído para você.
        </p>

        <div className="lp-hero-acoes">
          <a
            className="lp-btn lp-btn-primario"
            href="#planos"
            data-testid="landing-primary-cta"
            id="landing-conhecer-os-planos"
          >
            Conhecer os planos <ArrowRight size={16} aria-hidden="true" />
          </a>
          <button
            type="button"
            className="lp-btn lp-btn-fantasma"
            onClick={onEntrar}
            data-testid="landing-hero-login"
            id="landing-ja-tenho-conta"
            name="ja-tenho-conta"
          >
            Já tenho conta <ArrowRight size={14} aria-hidden="true" />
          </button>
        </div>

        <p className="lp-hero-linha">
          Treino personalizado <i aria-hidden="true">·</i> Nutrição{" "}
          <i aria-hidden="true">·</i> Progressão
        </p>

        <LandingProductPreview />
      </section>

      <LandingStorytelling />

      <section className="lp-secao" id="metodo">
        <div className="lp-secao-titulo">
          <p className="lp-eyebrow">O método</p>
          <h2>
            Do zero ao primeiro treino <em>no mesmo dia.</em>
          </h2>
        </div>
        <ol className="lp-passos">
          {PASSOS.map((p) => (
            <li key={p.n}>
              <span className="lp-passo-n">{p.n}</span>
              <div>
                <h3>{p.titulo}</h3>
                <p>{p.texto}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="lp-secao" id="planos">
        <div className="lp-secao-titulo">
          <p className="lp-eyebrow">Planos</p>
          <h2>
            Escolha o seu <em>nível de precisão.</em>
          </h2>
          <p className="lp-secao-lead">
            Assinatura mensal. Você escolhe o plano antes de criar a conta e pode trocar
            antes de pagar.
          </p>
        </div>

        {carregando && <p className="lp-aviso">Carregando planos...</p>}
        {erro && <p className="lp-erro">{erro}</p>}

        <div className="lp-planos">
          {planos.map((p) => (
            <Plano key={p.code} plano={p} onComecar={onComecar} />
          ))}
        </div>

        <p className="lp-nota">
          <ShieldCheck size={14} aria-hidden="true" /> Pagamento processado pelo Mercado
          Pago. O FORGE não armazena dados do seu cartão.
        </p>
      </section>

      <section className="lp-fechamento">
        <h2>
          Seu treino deixa de ser <em>um palpite.</em>
        </h2>
        <div className="lp-hero-acoes">
          <button
            type="button"
            className="lp-btn lp-btn-primario"
            onClick={() => onComecar("")}
            data-testid="landing-final-cta"
            id="landing-comecar-agora"
            name="comecar-agora"
          >
            Começar agora <ArrowRight size={16} aria-hidden="true" />
          </button>
          <button
            type="button"
            className="lp-btn lp-btn-fantasma"
            onClick={onEntrar}
            data-testid="landing-footer-login"
            id="landing-ja-tenho-conta-rodape"
            name="ja-tenho-conta"
          >
            Já tenho conta <ArrowRight size={14} aria-hidden="true" />
          </button>
        </div>
      </section>

      <footer className="lp-rodape">
        <div className="lp-marca">
          <span className="lp-marca-selo">F</span> FORGE
        </div>
        <p>Advanced Training OS</p>
      </footer>
    </div>
  );
}
