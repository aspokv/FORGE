import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowRight } from "lucide-react";

import telaInicio from "../../assets/forge-tela-inicio.webp";
import { CINEMATIC_CHAPTERS, chapterFromProgress } from "./sceneConfig";
import "./cinematic-landing.css";

const ForgePhoneScene = lazy(() => import("./ForgePhoneScene"));

function supportsWebGL() {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(window.WebGL2RenderingContext && canvas.getContext("webgl2"));
  } catch (_) {
    return false;
  }
}

export default function CinematicLanding({ onComecar }) {
  const sectionRef = useRef(null);
  const progressRef = useRef(0);
  const [chapter, setChapter] = useState(0);
  const [profile, setProfile] = useState("masculino");
  const [canRender, setCanRender] = useState(false);
  const [sceneReady, setSceneReady] = useState(false);

  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    setCanRender(!reduced && supportsWebGL());

    let frame = 0;
    const measure = () => {
      frame = 0;
      const section = sectionRef.current;
      if (!section) return;
      const rect = section.getBoundingClientRect();
      const travel = Math.max(section.offsetHeight - window.innerHeight, 1);
      const value = Math.max(0, Math.min(1, -rect.top / travel));
      progressRef.current = value;
      setChapter((old) => {
        const next = chapterFromProgress(value);
        return old === next ? old : next;
      });
    };
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(measure);
    };
    measure();
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
    };
  }, []);

  return (
    <section ref={sectionRef} className="cinematic" id="por-dentro" aria-label="FORGE por dentro">
      <div className="cinematic-sticky">
        <div className="cinematic-grid" aria-hidden="true" />
        <div className="cinematic-light cinematic-light-a" aria-hidden="true" />
        <div className="cinematic-light cinematic-light-b" aria-hidden="true" />

        <div className="cinematic-copy" aria-live="polite">
          {CINEMATIC_CHAPTERS.map((item, index) => (
            <article key={item.eyebrow} className={index === chapter ? "is-active" : ""}>
              <p className="lp-eyebrow">{item.eyebrow}</p>
              <h1>{item.title}</h1>
              <p>{item.text}</p>
              {index === 0 && (
                <div className="cinematic-actions">
                  <button type="button" className="lp-btn lp-btn-primario" onClick={() => onComecar("")}>
                    Construir meu plano <ArrowRight size={16} aria-hidden="true" />
                  </button>
                  <a href="#metodo">Conhecer o método <ArrowDown size={15} aria-hidden="true" /></a>
                </div>
              )}
            </article>
          ))}
        </div>

        <div className={`cinematic-product${sceneReady ? " is-ready" : ""}`}>
          <div className="cinematic-fallback" aria-hidden={canRender && sceneReady ? "true" : undefined}>
            <div className="cinematic-fallback-phone"><img src={telaInicio} alt="Tela inicial do FORGE" /></div>
          </div>
          {canRender && (
            <Suspense fallback={null}>
              <ForgePhoneScene progressRef={progressRef} profile={profile} onReady={() => setSceneReady(true)} />
            </Suspense>
          )}
          <p className="cinematic-rotate">Arraste para girar <span aria-hidden="true">360°</span></p>
        </div>

        <div className="cinematic-profile" aria-label="Perfil de treino">
          <span>Experiência por perfil</span>
          <div role="group" aria-label="Selecionar perfil">
            <button type="button" className={profile === "feminino" ? "active" : ""} onClick={() => setProfile("feminino")}>Feminino</button>
            <button type="button" className={profile === "masculino" ? "active" : ""} onClick={() => setProfile("masculino")}>Masculino</button>
          </div>
        </div>

        <ol className="cinematic-progress" aria-label="Progresso da apresentação">
          {CINEMATIC_CHAPTERS.map((item, index) => <li key={item.eyebrow} className={index === chapter ? "active" : ""}><span>{String(index + 1).padStart(2, "0")}</span></li>)}
        </ol>
      </div>
    </section>
  );
}
