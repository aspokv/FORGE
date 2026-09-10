/**
 * Concluir treino — exatamente uma conclusao por sessao.
 *
 * Mora fora do App.js para poder ser testado com o Jest que ja vem no react-scripts,
 * sem instalar biblioteca de renderizacao. As dependencias (post, now) entram por
 * parametro justamente para o teste nao precisar de axios nem de rede.
 *
 * Tres regras que a versao anterior quebrava:
 *
 *  1. Nao inventar recovery. O antigo POST /recovery disparado aqui com valores fixos
 *     (sleep 4, energy 3, soreness 2, stress 2) dava score 3*2-2-2 = 2 no motor, abaixo
 *     do limiar 3, marcando o atleta como VERY_LOW: -2 series em cada exercicio e RIR
 *     "3+" no programa inteiro, para sempre, sem ele ter respondido nada. Sem registro
 *     nenhum o motor assume NORMAL, que e o comportamento honesto. Recovery so deve ser
 *     gravado a partir de resposta real do atleta, por um fluxo proprio.
 *
 *  2. A trava do duplo clique e sincrona (um ref, nao um estado do React): dois toques
 *     no celular chegam no mesmo tick, antes de qualquer re-render, entao um setState
 *     nao chegaria a tempo de barrar o segundo.
 *
 *  3. Sucesso so depois da resposta confirmada do servidor. Antes, o resultado de
 *     sucesso era escrito fora do caminho de sucesso: a API falhava e a tela ainda
 *     comemorava "series registradas" por cima de nada persistido.
 */

export const SEM_SERIES = "Complete pelo menos uma série para concluir.";
export const FALHOU = "Não foi possível concluir o treino. Tente novamente.";
export const WORKOUT_COMPLETION_STORAGE_PREFIX = "forge_workout_completion:";
export const completionStorageKey = userId => `${WORKOUT_COMPLETION_STORAGE_PREFIX}${String(userId||"")}`;

function currentUserIdFromToken() {
  if (typeof window === "undefined") return "";
  try {
    const token = window.localStorage.getItem("forge_token") || "";
    const payload = token.split(".")[1];
    if (!payload) return "";
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
    return String(JSON.parse(window.atob(padded))?.sub || "");
  } catch {
    return "";
  }
}

function persistConfirmedCompletion(data, fallbackDay, now) {
  if (typeof window === "undefined") return;
  const userId = currentUserIdFromToken();
  if (!userId) return;
  try {
    const completedAt = new Date(now()).toISOString();
    const record = {
      completed_at: completedAt,
      day: data?.completed_day ?? data?.completed_session?.day ?? fallbackDay ?? null,
      label: data?.completed_session?.label || null,
      summary: data?.summary || null,
    };
    window.localStorage.setItem(completionStorageKey(userId), JSON.stringify(record));
  } catch {
    // Cache local e apenas um espelho de UX. A conclusao real ja foi confirmada no backend.
  }
}

/**
 * @returns objeto de sucesso {completed,total,minutes}; {error:true,message} em falha;
 *          ou null quando o toque foi ignorado por ja haver uma conclusao em voo.
 */
export async function completeWorkout({
  post, api, day, completedSets, totalSets, startedAt, lock, onCompleted,
  partialReason = "", discomfort = "none", volumeKg = 0, averageRir = null,
  now = Date.now,
}) {
  if (!completedSets) return { error: true, message: SEM_SERIES };
  if (lock.current) return null;
  lock.current = true;
  try {
    const durationSeconds = Math.max(1, Math.round((now() - startedAt) / 1000));
    const r = await post(`${api}/workout/complete`, {
      day,
      completed_sets: completedSets,
      total_sets: totalSets,
      duration_seconds: durationSeconds,
      started_at: new Date(startedAt).toISOString(),
      partial_reason: partialReason,
      discomfort,
    });
    persistConfirmedCompletion(r.data, day, now);
    if (onCompleted) onCompleted(r.data);
    if (typeof window !== "undefined") window.dispatchEvent(new Event("forge:workout-complete"));
    // Trava mantida de proposito no sucesso: o botao sai da tela enquanto ela atualiza,
    // e liberar aqui reabriria a janela para um segundo toque atrasado.
    return {
      completed: completedSets,
      total: totalSets,
      minutes: Math.max(1, Math.round(durationSeconds / 60)),
      volumeKg: Math.round(volumeKg),
      averageRir,
      nextSession: r.data?.next_session || null,
      completedSession: r.data?.completed_session || null,
      adherence: r.data?.summary?.adherence_pct ?? Math.round(completedSets / Math.max(1, totalSets) * 100),
    };
  } catch (e) {
    lock.current = false;
    // So texto vindo do proprio backend (mensagens curadas, em portugues). Qualquer
    // outra coisa vira a mensagem generica: nada de stack trace, corpo cru ou token.
    const detail = e?.response?.data?.detail;
    return { error: true, message: typeof detail === "string" && detail ? detail : FALHOU };
  }
}
