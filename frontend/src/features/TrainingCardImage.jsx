import {useState} from "react";
import {resolveTrainingArtwork, trainingArtworkAlt} from "./trainingCardArtwork";

function ArtworkImage({artwork, ...props}) {
  const [index, setIndex] = useState(0);
  const candidate = artwork.candidates[index];
  if (!candidate) return <span className={props.className} aria-hidden="true" />;
  return <img {...props} src={candidate.src} alt={trainingArtworkAlt(candidate)}
    data-training-category={artwork.category} data-training-profile={candidate.profile}
    decoding="async" onError={() => setIndex(value => value + 1)} />;
}

export default function TrainingCardImage({session, program, profile, focus, ...props}) {
  const artwork = resolveTrainingArtwork({session, program, profile, focus});
  return <ArtworkImage key={artwork.candidates.map(item => item.src).join("|")} artwork={artwork} {...props} />;
}
