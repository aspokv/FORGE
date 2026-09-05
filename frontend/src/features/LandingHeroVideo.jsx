import { useEffect, useRef, useState } from "react";

import posterHero from "../assets/forge-hero-poster.webp";
import videoHero from "../assets/forge-hero.mp4";

/**
 * O visual do hero: o filme vertical da marca.
 *
 * Substitui a composicao de tres celulares que ocupava este lugar. As telas do aplicativo
 * continuam na pagina, no storytelling logo abaixo — o hero passa a abrir com o filme, e
 * o produto por dentro vem em seguida.
 *
 * O filme e 1080x1920 e traz a propria tipografia gravada ("DISCIPLINA TRANSFORMA
 * REALIDADES") e o logo no fim. Por isso ele NAO vira fundo atras do titulo da pagina:
 * duas tipografias sobrepostas brigariam e nenhuma das duas seria lida. Ele ocupa um
 * painel proprio, em retrato, com a mesma moldura das telas do resto da landing.
 *
 * O painel e medido pela ALTURA (`min(72vh, 700px)`), e nao pela largura. E o que garante
 * as duas exigencias ao mesmo tempo: o filme nunca estoura a altura do hero, e a largura
 * sai da proporcao, entao nunca ha deformacao nem barra horizontal.
 */

/** Quem pediu menos movimento, ou esta economizando dados, recebe so o poster. */
function devePular() {
  if (typeof window === "undefined") return false;
  const menosMovimento = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
  const economia = navigator.connection?.saveData === true;
  return Boolean(menosMovimento || economia);
}

export default function LandingHeroVideo() {
  const video = useRef(null);
  const [pronto, setPronto] = useState(false);
  const [semVideo, setSemVideo] = useState(false);

  useEffect(() => {
    if (devePular()) {
      // Cinco megabytes nao sao baixados a toa: sem o `src`, o navegador nao pede o
      // arquivo, e o poster ja e a imagem final.
      setSemVideo(true);
      return undefined;
    }

    const el = video.current;
    if (!el) return undefined;

    const aoPoder = () => setPronto(true);
    const aoFalhar = () => setSemVideo(true);
    el.addEventListener("canplay", aoPoder);
    el.addEventListener("error", aoFalhar);

    // `muted` no atributo E na propriedade: o Safari decide o autoplay pela propriedade, e
    // sem ela a promessa de play e recusada. Recusa nao e erro — o poster segue no lugar.
    el.muted = true;
    const p = el.play?.();
    if (p && typeof p.catch === "function") p.catch(() => {});

    return () => {
      el.removeEventListener("canplay", aoPoder);
      el.removeEventListener("error", aoFalhar);
    };
  }, []);

  return (
    <div className="lp-filme" data-pronto={pronto ? "sim" : "nao"}>
      <div className="lp-filme-quadro">
        <img
          className="lp-filme-poster"
          src={posterHero}
          alt="FORGE — disciplina transforma realidades."
          width="540"
          height="960"
          fetchpriority="high"
          decoding="async"
        />
        {!semVideo && (
          <video
            ref={video}
            className="lp-filme-video"
            // Sem `controls`: e peca de cena, nao player.
            autoPlay
            muted
            loop
            playsInline
            preload="auto"
            poster={posterHero}
            aria-hidden="true"
            tabIndex={-1}
          >
            <source src={videoHero} type="video/mp4" />
          </video>
        )}
      </div>
    </div>
  );
}
