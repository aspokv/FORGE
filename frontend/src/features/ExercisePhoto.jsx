import {useState} from "react";
import {Dumbbell} from "lucide-react";
import {reviewedArtworkForExercise} from "./reviewedExerciseArtwork";
import "./exercise-artwork.css";

export default function ExercisePhoto({exercise={},className=""}){
  const src=reviewedArtworkForExercise(exercise);
  const [failedSrc,setFailedSrc]=useState(null);
  const valid=src&&failedSrc!==src;
  const label=exercise.name||exercise.id||exercise.exercise_id||"Exercício";
  return <div className={`ref3-ex-art exercise-photo ${className}${valid?"":" fallback"}`} role="img" aria-label={`Ilustração de ${label}`}>
    {valid?<img className="ref3-reviewed-art" src={src} alt="" aria-hidden="true" loading="lazy" decoding="async" onError={()=>setFailedSrc(src)}/>:<Dumbbell size={27}/>}
  </div>;
}
