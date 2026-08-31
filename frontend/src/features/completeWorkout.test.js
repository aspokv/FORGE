/**
 * Fluxo "Concluir treino" — os tres bugs que este modulo existe para impedir:
 * recovery fabricado, duplo toque virando duas conclusoes, e sucesso falso quando
 * a API falha.
 */
import {completeWorkout, FALHOU, SEM_SERIES} from "./completeWorkout";

const base = (post, over = {}) => ({
  post, api: "/api", day: 1,
  completedSets: 3, totalSets: 4,
  startedAt: 0, now: () => 120000,
  lock: {current: false},
  onCompleted: () => {},
  ...over,
});

const ok = () => jest.fn().mockResolvedValue({data: {next_day: 2}});
const falha = () => jest.fn().mockRejectedValue(new Error("network down"));
const pendente = () => {
  let resolve, reject;
  const post = jest.fn(() => new Promise((res, rej) => { resolve = res; reject = rej; }));
  return {post, resolve: v => resolve(v), reject: e => reject(e)};
};

describe("um toque", () => {
  it("dispara exatamente uma requisicao, para /workout/complete", async () => {
    const post = ok();
    await completeWorkout(base(post));
    expect(post).toHaveBeenCalledTimes(1);
    expect(post.mock.calls[0][0]).toBe("/api/workout/complete");
    expect(post.mock.calls[0][1]).toEqual({
      day: 1,
      completed_sets: 3,
      total_sets: 4,
      duration_seconds: 120,
      started_at: "1970-01-01T00:00:00.000Z",
      partial_reason: "",
      discomfort: "none",
    });
  });

  it("devolve o resumo da sessao com os minutos decorridos", async () => {
    const r = await completeWorkout(base(ok()));
    expect(r).toEqual({
      completed: 3, total: 4, minutes: 2, volumeKg: 0, averageRir: null,
      nextSession: null, completedSession: null, adherence: 75,
    });
  });
});

describe("recovery fabricado (bug 1)", () => {
  it("nao envia recovery nenhum ao concluir", async () => {
    const post = ok();
    await completeWorkout(base(post));
    const urls = post.mock.calls.map(c => c[0]);
    expect(urls).toEqual(["/api/workout/complete"]);
    expect(urls.some(u => u.includes("recovery"))).toBe(false);
  });

  it("nao manda sleep/energy/soreness/stress em corpo nenhum", async () => {
    const post = ok();
    await completeWorkout(base(post));
    const corpos = JSON.stringify(post.mock.calls.map(c => c[1]));
    expect(corpos).not.toMatch(/sleep|energy|soreness|stress/);
  });
});

describe("duplo toque (bug 2)", () => {
  it("dois toques no mesmo tick produzem uma unica requisicao", async () => {
    const {post, resolve} = pendente();
    const args = base(post);
    const p1 = completeWorkout(args);
    const p2 = completeWorkout(args); // antes de qualquer re-render
    resolve({data: {}});
    const [r1, r2] = await Promise.all([p1, p2]);
    expect(post).toHaveBeenCalledTimes(1);
    expect(r2).toBeNull();            // toque descartado: nao vira resultado na tela
    expect(r1).toMatchObject({completed: 3});
  });

  it("a trava fica ativa durante o voo e continua ativa apos o sucesso", async () => {
    const {post, resolve} = pendente();
    const lock = {current: false};
    const p = completeWorkout(base(post, {lock}));
    expect(lock.current).toBe(true);
    resolve({data: {}});
    await p;
    expect(lock.current).toBe(true);  // botao sai da tela; nao reabrir a janela
  });
});

describe("falha da API (bug 3)", () => {
  it("nao produz sucesso e nao confirma a conclusao", async () => {
    const onCompleted = jest.fn();
    const r = await completeWorkout(base(falha(), {onCompleted}));
    expect(onCompleted).not.toHaveBeenCalled();
    expect(r.completed).toBeUndefined();
    expect(r).toEqual({error: true, message: FALHOU});
  });

  it("libera a trava e a tentativa seguinte funciona", async () => {
    const lock = {current: false};
    const r1 = await completeWorkout(base(falha(), {lock}));
    expect(r1.error).toBe(true);
    expect(lock.current).toBe(false);

    const post2 = ok();
    const r2 = await completeWorkout(base(post2, {lock}));
    expect(post2).toHaveBeenCalledTimes(1);
    expect(r2.error).toBeUndefined();
  });

  it("mostra a mensagem curada do backend quando ela e texto", async () => {
    const {post, reject} = pendente();
    const p = completeWorkout(base(post));
    reject({response: {data: {detail: "Nenhuma sessao disponivel para concluir"}}});
    expect((await p).message).toBe("Nenhuma sessao disponivel para concluir");
  });

  it("nao vaza detalhe interno, stack ou token", async () => {
    const {post, reject} = pendente();
    const p = completeWorkout(base(post));
    reject({response: {data: {detail: {stack: "Traceback (most recent call last)", token: "eyJhbG"}}}});
    const r = await p;
    expect(r.message).toBe(FALHOU);
    expect(JSON.stringify(r)).not.toMatch(/Traceback|eyJhbG/);
  });
});

describe("sem serie registrada", () => {
  it("nao chama a API e explica o motivo", async () => {
    const post = ok();
    const r = await completeWorkout(base(post, {completedSets: 0}));
    expect(post).not.toHaveBeenCalled();
    expect(r).toEqual({error: true, message: SEM_SERIES});
  });

  it("nao consome a trava", async () => {
    const lock = {current: false};
    await completeWorkout(base(ok(), {completedSets: 0, lock}));
    expect(lock.current).toBe(false);
  });
});
