import { sequenciaDeDias, volumeDaSemana, textoDaCarga, textoDeProntidao } from "./ritmoDaSemana";

/** Uma serie registrada no dia indicado, com carga e repeticoes opcionais. */
const serie = (iso, weight, reps) => ({ created_at: `${iso}T10:00:00`, weight, reps });

describe("sequenciaDeDias", () => {
  test("conta dias seguidos terminando hoje", () => {
    const hoje = new Date("2026-09-13T20:00:00");
    const sets = [serie("2026-09-13"), serie("2026-09-12"), serie("2026-09-11")];
    expect(sequenciaDeDias(sets, hoje)).toBe(3);
  });

  test("varias series no mesmo dia contam como um dia so", () => {
    const hoje = new Date("2026-09-13T20:00:00");
    const sets = [serie("2026-09-13"), serie("2026-09-13"), serie("2026-09-13")];
    expect(sequenciaDeDias(sets, hoje)).toBe(1);
  });

  // Quem treina de manha nao pode perder a sequencia so porque ainda nao treinou hoje.
  test("segue valendo quando o ultimo treino foi ontem", () => {
    const hoje = new Date("2026-09-13T06:00:00");
    const sets = [serie("2026-09-12"), serie("2026-09-11")];
    expect(sequenciaDeDias(sets, hoje)).toBe(2);
  });

  test("zera quando o ultimo treino foi anteontem", () => {
    const hoje = new Date("2026-09-13T20:00:00");
    expect(sequenciaDeDias([serie("2026-09-11")], hoje)).toBe(0);
  });

  test("um buraco no meio interrompe a contagem", () => {
    const hoje = new Date("2026-09-13T20:00:00");
    const sets = [serie("2026-09-13"), serie("2026-09-12"), serie("2026-09-10")];
    expect(sequenciaDeDias(sets, hoje)).toBe(2);
  });

  test("sem serie nenhuma a sequencia e zero", () => {
    expect(sequenciaDeDias([], new Date())).toBe(0);
    expect(sequenciaDeDias(undefined, new Date())).toBe(0);
  });

  test("data invalida nao quebra nem entra na conta", () => {
    const hoje = new Date("2026-09-13T20:00:00");
    const sets = [{ created_at: "nao e data" }, serie("2026-09-13")];
    expect(sequenciaDeDias(sets, hoje)).toBe(1);
  });
});

describe("volumeDaSemana", () => {
  const segunda = new Date("2026-09-07T00:00:00");

  test("soma series e carga a partir da segunda", () => {
    const sets = [serie("2026-09-08", 60, 10), serie("2026-09-09", 80, 5)];
    expect(volumeDaSemana(sets, segunda)).toEqual({ series: 2, kg: 1000 });
  });

  test("ignora o que e anterior a segunda", () => {
    const sets = [serie("2026-09-06", 100, 10), serie("2026-09-08", 60, 10)];
    expect(volumeDaSemana(sets, segunda)).toEqual({ series: 1, kg: 600 });
  });

  // O campo e de texto e a pessoa digita virgula. Number("62,5") e NaN.
  test("aceita carga com virgula", () => {
    expect(volumeDaSemana([serie("2026-09-08", "62,5", "4")], segunda).kg).toBe(250);
  });

  test("peso do corpo conta como serie sem somar carga", () => {
    const sets = [serie("2026-09-08", null, 12), serie("2026-09-08", 50, 10)];
    expect(volumeDaSemana(sets, segunda)).toEqual({ series: 2, kg: 500 });
  });

  test("semana vazia devolve zeros", () => {
    expect(volumeDaSemana([], segunda)).toEqual({ series: 0, kg: 0 });
  });
});

describe("textoDaCarga", () => {
  test("abaixo de mil quilos fica em kg", () => {
    expect(textoDaCarga(840)).toBe("840 kg");
  });

  test("a partir de mil vira tonelada", () => {
    expect(textoDaCarga(8400)).toBe("8,4 t");
  });

  test("sem carga nao inventa numero", () => {
    expect(textoDaCarga(0)).toBe("—");
  });
});

describe("textoDeProntidao", () => {
  test("cada nivel do motor tem rotulo proprio", () => {
    expect(textoDeProntidao("HIGH").rotulo).toBe("Alta");
    expect(textoDeProntidao("NORMAL").rotulo).toBe("Normal");
    expect(textoDeProntidao("LOW").rotulo).toBe("Baixa");
    expect(textoDeProntidao("VERY_LOW").rotulo).toBe("Muito baixa");
  });

  // O texto tem de explicar o treino menor, senao a pessoa acha que faltou algo.
  test("nivel baixo avisa que o motor aliviou o treino", () => {
    expect(textoDeProntidao("LOW").efeito).toMatch(/aliviou/i);
    expect(textoDeProntidao("VERY_LOW").efeito).toMatch(/reduziu/i);
  });

  test("nivel desconhecido cai em normal em vez de quebrar", () => {
    expect(textoDeProntidao(undefined).rotulo).toBe("Normal");
    expect(textoDeProntidao("XPTO").rotulo).toBe("Normal");
  });
});
