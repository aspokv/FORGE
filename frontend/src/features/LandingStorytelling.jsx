import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import telaTreino from "../assets/forge-tela-treino.webp";
import telaNutricao from "../assets/forge-tela-nutricao.webp";
import telaInicio from "../assets/forge-tela-inicio.webp";
import telaProgresso from "../assets/forge-tela-progresso.webp";

/**
 * O storytelling: o painel fica preso na tela e o scroll vertical dirige a passagem
 * horizontal das telas reais do FORGE.
 *
 *   Treino -> Nutricao -> Inicio -> Progresso
 *
 * O hero mostra as tres juntas; aqui elas se separam e cada area e explicada sozinha.
 *
 * Sem biblioteca de animacao: um ouvinte de scroll passivo e um laco de quadro proprio.
 * O projeto nao tem GSAP e a alternativa seria adicionar uma dependencia inteira para uma
 * conta de tres linhas. O framer-motion, que existe aqui, faria o valor passar pelo estado
 * do React a cada quadro — caro justamente no celular, que e onde a pagina precisa ser boa.
 */

/* ---- Geometria do trilho -------------------------------------------------- */

/**
 * Distancia entre dois celulares, como fracao da largura de um.
 *
 * 0,82 e a sobreposicao da composicao de referencia: o celular lateral cobre cerca de 15%
 * do central. E a sobreposicao que faz a fila parecer profundidade, e nao tres pecas
 * enfileiradas.
 */
const ESPACO = 0.82;
const ANGULO = 26; // graus de inclinacao por passo de distancia
const PROFUNDIDADE = 150; // px de recuo em Z por passo
const ENCOLHE = 0.075;
const ESCURECE = 0.58; // veu sobre a tela vizinha
const LIMITE = 2.2; // onde giro, recuo, escala e veu saturam
const SOME_DE = 1.25;
const SOME_ATE = 1.75;

/**
 * Espera e movimento alternados, em unidades arbitrarias.
 *
 * A tela encaixa no centro, FICA (e onde se le a legenda) e so entao desliza. Distribuir
 * o progresso linearmente transformava o painel num borrao continuo, sem passos.
 */
const ESPERA = 0.85;
const MOVE = 1.15;

export const TELAS = [
  {
    id: "treino",
    src: telaTreino,
    aba: "Treino",
    indice: "01",
    titulo: "O treino de hoje já está montado.",
    texto:
      "Divisão, exercícios, séries e cargas decididos a partir da sua avaliação. " +
      "Você abre o aplicativo e começa.",
    alt: "Tela de treino do FORGE: peitoral e ombros, 60 minutos, com a lista de exercícios e séries.",
  },
  {
    id: "nutricao",
    src: telaNutricao,
    aba: "Nutrição",
    indice: "02",
    titulo: "A alimentação que sustenta o treino.",
    texto:
      "Refeições com meta calórica e macros, prontas para o dia. Faltou um alimento? " +
      "A substituição equivalente mantém o plano de pé.",
    alt: "Tela de nutrição do FORGE: café da manhã, almoço e lanche com calorias e porções.",
  },
  {
    id: "inicio",
    src: telaInicio,
    aba: "Início",
    indice: "03",
    titulo: "O dia inteiro em uma tela.",
    texto:
      "Treino, calorias, água e a semana em andamento. Você sabe o que falta sem " +
      "precisar procurar.",
    alt: "Tela inicial do FORGE: resumo da semana, plano de hoje, nutrição e hidratação.",
  },
  {
    id: "progresso",
    src: telaProgresso,
    aba: "Progresso",
    indice: "04",
    titulo: "A evolução fica registrada, não na sua memória.",
    texto:
      "Cargas por semana, onde o estímulo se concentra e quantos dias você realmente " +
      "treinou. É daqui que sai o ajuste do próximo ciclo.",
    alt: "Tela de progresso do FORGE: cargas por semana, mapa de estímulo e consistência de 28 dias.",
  },
];

const TOTAL = TELAS.length * ESPERA + (TELAS.length - 1) * MOVE;

const limitar = (v, min, max) => (v < min ? min : v > max ? max : v);

/** Smootherstep: parte e chega com derivada zero. E o que da a sensacao de encaixe. */
const suave = (x) => x * x * x * (x * (x * 6 - 15) + 10);

/**
 * Progresso do scroll (0..1) -> posicao no trilho (0..N-1).
 * Inteiro = tela encaixada no centro. Fracionario = em transito.
 */
function posicaoDoTrilho(t) {
  let u = limitar(t, 0, 1) * TOTAL;
  for (let i = 0; i < TELAS.length; i += 1) {
    if (u < ESPERA) return i;
    u -= ESPERA;
    if (i === TELAS.length - 1) return i;
    if (u < MOVE) return i + suave(u / MOVE);
    u -= MOVE;
  }
  return TELAS.length - 1;
}

/**
 * Distancia circular ate o centro, em passos.
 *
 * O trilho fecha em circulo, e nao em fila. Numa fila, a primeira parada nao teria nada a
 * esquerda e a composicao ficaria encostada a direita — o oposto do hero, onde a tela
 * central sempre tem uma vizinha de cada lado. Fechado, o enquadramento e o mesmo nas
 * quatro paradas.
 */
function distanciaCircular(i, p, total) {
  const meia = total / 2;
  return ((((i - p + meia) % total) + total) % total) - meia;
}

/**
 * O estado visual de uma tela.
 *
 * So o deslocamento em X acompanha `d` sem teto — e ele que tira a tela da cena. O resto
 * satura em LIMITE: sem isso a tela mais distante chegaria de perfil e viraria um risco
 * vertical em vez de profundidade.
 *
 * `opacidade` existe por causa do circulo: no ponto oposto ao centro a distancia salta de
 * -2 para +2 e a tela troca de lado de uma vez. O salto e inevitavel; o que nao pode e ser
 * visto. Ela some antes de chegar la e volta ja do outro lado.
 */
function estadoDaTela(d, larguraDoFone) {
  const bruta = Math.abs(d);
  const dist = Math.min(bruta, LIMITE);
  return {
    x: d * larguraDoFone * ESPACO,
    z: -dist * PROFUNDIDADE,
    giro: Math.sign(d) * dist * ANGULO,
    escala: 1 - dist * ENCOLHE,
    veu: Math.min(dist * ESCURECE, 0.9),
    opacidade: 1 - limitar((bruta - SOME_DE) / (SOME_ATE - SOME_DE), 0, 1),
  };
}

/* ---- Componente ----------------------------------------------------------- */

export default function LandingStorytelling() {
  const secao = useRef(null);
  const fones = useRef([]);
  const veus = useRef([]);
  const legenda = useRef(null);
  const quadro = useRef(0);

  // Muda quatro vezes na secao inteira — aqui estado do React e barato e correto.
  const [ativo, setAtivo] = useState(0);
  const ativoRef = useRef(0);
  const [semMovimento, setSemMovimento] = useState(false);

  const aplicar = useCallback(function posicionar(p, tentativa = 0) {
    const primeiro = fones.current[0];
    if (!primeiro) return;

    // Antes de o layout resolver, a largura e zero e o espacamento sairia errado. Adia um
    // quadro em vez de posicionar sobre medida invalida. O teto evita laco infinito se a
    // secao estiver oculta.
    const largura = primeiro.offsetWidth;
    if (!largura) {
      if (tentativa < 60) requestAnimationFrame(() => posicionar(p, tentativa + 1));
      return;
    }

    fones.current.forEach((el, i) => {
      if (!el) return;
      const s = estadoDaTela(distanciaCircular(i, p, TELAS.length), largura);
      el.style.transform =
        `translate(-50%, -50%) translate3d(${s.x.toFixed(2)}px, 0, ${s.z.toFixed(2)}px) ` +
        `rotateY(${s.giro.toFixed(2)}deg) scale(${s.escala.toFixed(4)})`;
      el.style.opacity = s.opacidade.toFixed(3);
      // O empilhamento segue a distancia, senao a ordem do documento contradiz a
      // perspectiva e a tela de tras aparece na frente.
      el.style.zIndex = String(100 - Math.round(Math.abs(s.x) / 10));
      if (veus.current[i]) veus.current[i].style.opacity = s.veu.toFixed(3);
    });

    // A legenda pertence a tela parada: some no transito e volta no encaixe.
    const perto = Math.round(p);
    const fracao = Math.abs(p - perto);
    if (legenda.current) {
      legenda.current.style.opacity = limitar(1 - fracao * 2.6, 0, 1).toFixed(3);
    }
    if (perto !== ativoRef.current) {
      ativoRef.current = perto;
      setAtivo(perto);
    }
  }, []);

  // Estado inicial antes da primeira pintura, para a secao nao piscar empilhada.
  useLayoutEffect(() => {
    aplicar(0);
  }, [aplicar]);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const aoMudar = (e) => setSemMovimento(e.matches);
    setSemMovimento(mq.matches);
    mq.addEventListener("change", aoMudar);
    return () => mq.removeEventListener("change", aoMudar);
  }, []);

  useEffect(() => {
    if (semMovimento) return undefined;

    // Amortecimento proprio: o valor perseguido persegue o do scroll, o que da o mesmo
    // "scrub" macio de uma biblioteca sem trazer uma. `alvo` e onde o dedo esta; `atual` e
    // onde o painel esta.
    let alvo = 0;
    let atual = 0;
    let ultimo = performance.now();

    const medir = () => {
      const el = secao.current;
      if (!el) return 0;
      const curso = el.offsetHeight - window.innerHeight;
      if (curso <= 0) return 0;
      return limitar((window.scrollY - el.offsetTop) / curso, 0, 1);
    };

    const passo = (agora) => {
      const dt = Math.min((agora - ultimo) / 1000, 0.05);
      ultimo = agora;
      // Amortecimento independente da taxa de quadros: em 30fps e em 144fps o painel
      // chega no mesmo tempo, em vez de ficar lento na tela lenta.
      atual += (alvo - atual) * (1 - Math.exp(-9 * dt));
      if (Math.abs(alvo - atual) < 0.00002) atual = alvo;
      aplicar(posicaoDoTrilho(atual));
      quadro.current = requestAnimationFrame(passo);
    };

    const aoRolar = () => {
      alvo = medir();
    };

    alvo = medir();
    atual = alvo;
    quadro.current = requestAnimationFrame(passo);
    window.addEventListener("scroll", aoRolar, { passive: true });
    window.addEventListener("resize", aoRolar);

    return () => {
      cancelAnimationFrame(quadro.current);
      window.removeEventListener("scroll", aoRolar);
      window.removeEventListener("resize", aoRolar);
    };
  }, [semMovimento, aplicar]);

  if (semMovimento) {
    // Mesma informacao, empilhada, sem prender o scroll.
    return (
      <section className="lp-story lp-story-parado" id="por-dentro">
        <ul>
          {TELAS.map((t) => (
            <li key={t.id}>
              <img src={t.src} alt={t.alt} width="504" height="1168" loading="lazy" />
              <p className="lp-eyebrow">
                {t.indice} / {t.aba}
              </p>
              <h3>{t.titulo}</h3>
              <p className="lp-story-texto">{t.texto}</p>
            </li>
          ))}
        </ul>
      </section>
    );
  }

  const tela = TELAS[ativo];

  return (
    <section
      ref={secao}
      className="lp-story"
      id="por-dentro"
      aria-label="As telas do FORGE"
    >
      <div className="lp-story-preso">
        <div className="lp-brilho" aria-hidden="true" />

        <header className="lp-abas">
          <ol>
            {TELAS.map((t, i) => (
              <li key={t.id} className={i === ativo ? "ativa" : ""}>
                <span aria-current={i === ativo ? "true" : undefined}>{t.aba}</span>
                <i aria-hidden="true" />
              </li>
            ))}
          </ol>
        </header>

        {/* `perspective` no palco, e nao em cada peca: um unico ponto de fuga para todas,
            senao cada celular parece fotografado por uma camera diferente. */}
        <div className="lp-story-palco">
          {TELAS.map((t, i) => (
            <div
              key={t.id}
              className="lp-story-fone"
              ref={(el) => (fones.current[i] = el)}
            >
              <img src={t.src} alt={t.alt} width="504" height="1168" decoding="async" />
              <span
                className="lp-veu"
                aria-hidden="true"
                ref={(el) => (veus.current[i] = el)}
              />
            </div>
          ))}
        </div>

        <footer className="lp-story-legenda" ref={legenda}>
          <p className="lp-eyebrow">
            {tela.indice} / {tela.aba}
          </p>
          <h3>{tela.titulo}</h3>
          <p className="lp-story-texto">{tela.texto}</p>
        </footer>
      </div>
    </section>
  );
}
