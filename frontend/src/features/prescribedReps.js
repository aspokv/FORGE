// Slash-separated prescriptions represent successive sets, not numeric input values.
export function prescribedReps(reps, setIndex=0) {
  const parts=String(reps||"").split("/");
  const selected=parts[Math.min(setIndex,parts.length-1)];
  const number=selected.match(/\d+/)?.[0];
  return number||""; // Failure/time without a numeric target must be entered by the athlete.
}
