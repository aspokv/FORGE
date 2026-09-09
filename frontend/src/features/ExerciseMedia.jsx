import {useEffect,useState} from "react";
import {createPortal} from "react-dom";
import {Dumbbell,X} from "lucide-react";
import {
  EXTERNAL_EXERCISE_MEDIA_ENABLED,
  exerciseMediaFor,
  joinMediaUrl,
} from "../data/exerciseMediaMap";
import {reviewedArtworkForExercise} from "./reviewedExerciseArtwork";
import "./exercise-artwork.css";
import "./exercise-media.css";

export default function ExerciseMedia({
  exercise={},
  className="",
  externalMediaEnabled=EXTERNAL_EXERCISE_MEDIA_ENABLED,
  mediaBaseUrl="",
  allowEquivalent=false,
}){
  const mapping=exerciseMediaFor(exercise);
  const mappedMatchAllowed=mapping?.match==="exact"||(allowEquivalent&&mapping?.match==="equivalent");
  const mappedAllowed=externalMediaEnabled&&mappedMatchAllowed&&Boolean(mediaBaseUrl);
  const mappedThumbnail=mappedAllowed?joinMediaUrl(mediaBaseUrl,mapping.thumbnail):null;
  const mappedAnimation=mappedAllowed?joinMediaUrl(mediaBaseUrl,mapping.animation):null;
  const forgeThumbnail=reviewedArtworkForExercise(exercise);
  const [failedSources,setFailedSources]=useState([]);
  const [animationOpen,setAnimationOpen]=useState(false);
  const [animationFailed,setAnimationFailed]=useState(false);
  const label=exercise.name||exercise.exercise_id||exercise.id||"Exercício";

  const source=mappedThumbnail&&!failedSources.includes(mappedThumbnail)
    ? mappedThumbnail
    : forgeThumbnail&&!failedSources.includes(forgeThumbnail)
      ? forgeThumbnail
      : null;
  const usesMappedThumbnail=Boolean(mappedThumbnail)&&source===mappedThumbnail;
  const canAnimate=usesMappedThumbnail&&Boolean(mappedAnimation);

  useEffect(()=>{
    if(!animationOpen)return undefined;
    const closeOnEscape=event=>{
      if(event.key==="Escape")setAnimationOpen(false);
    };
    document.addEventListener("keydown",closeOnEscape);
    return()=>document.removeEventListener("keydown",closeOnEscape);
  },[animationOpen]);

  const markFailed=failedSource=>setFailedSources(current=>current.includes(failedSource)?current:[...current,failedSource]);
  const openAnimation=()=>{
    setAnimationFailed(false);
    setAnimationOpen(true);
  };
  const closeAnimation=()=>setAnimationOpen(false);

  const still=source
    ? <img
        className="ref3-reviewed-art"
        src={source}
        alt=""
        aria-hidden="true"
        loading="lazy"
        decoding="async"
        onError={()=>markFailed(source)}
      />
    : <Dumbbell size={27}/>;

  const dialog=animationOpen&&typeof document!=="undefined"?createPortal(
    <div className="exercise-media-modal" role="presentation" onMouseDown={event=>{
      if(event.target===event.currentTarget)closeAnimation();
    }}>
      <section className="exercise-media-dialog" role="dialog" aria-modal="true" aria-label={`Execução de ${label}`}>
        <header>
          <div><span>EXECUÇÃO</span><strong>{label}</strong></div>
          <button type="button" onClick={closeAnimation} aria-label="Fechar execução"><X size={22}/></button>
        </header>
        <div className="exercise-media-animation">
          {!animationFailed
            ? <img src={mappedAnimation} alt={`Execução de ${label}`} onError={()=>setAnimationFailed(true)}/>
            : forgeThumbnail&&!failedSources.includes(forgeThumbnail)
              ? <img src={forgeThumbnail} alt={`Ilustração de ${label}`} onError={()=>markFailed(forgeThumbnail)}/>
              : <Dumbbell size={42}/>
          }
        </div>
        <a href="https://gymvisual.com/" target="_blank" rel="noreferrer">{mapping.attribution}</a>
        <button className="exercise-media-close" type="button" onClick={closeAnimation}>Fechar</button>
      </section>
    </div>,
    document.body,
  ):null;

  return <>
    <div
      className={`ref3-ex-art exercise-photo ${className}${source?"":" fallback"}${usesMappedThumbnail?" mapped":""}`}
      role={canAnimate?"group":"img"}
      aria-label={`Ilustração de ${label}`}
      data-media-source={usesMappedThumbnail?mapping.source:source?"forge":"fallback"}
    >
      {canAnimate
        ? <button className="exercise-media-trigger" type="button" onClick={openAnimation} aria-label={`Ver execução de ${label}`}>
            {still}
            <span className="exercise-media-trigger-label">Ver execução</span>
            <span className="exercise-media-attribution">© Gym visual — gymvisual.com</span>
          </button>
        : still
      }
    </div>
    {dialog}
  </>;
}
