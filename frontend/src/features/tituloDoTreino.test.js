/**
 * O nome da sessao nao pode partir no meio da palavra.
 *
 * O caso real: um atleta abriu o Inicio e leu "A ·/QUADRI/CEPS" em tres linhas. O titulo do
 * card tem tamanho fixo, mas o nome da sessao vem do programa e varia de "Push 1" a
 * "B · Posterior e Gluteos". CSS nao conta caractere, entao o degrau de tamanho e decidido
 * no componente — e e isto que este teste prende.
 *
 * A largura em si e verificada no navegador; aqui fica a REGRA, que e o que quebra em
 * silencio quando alguem mexer no limiar.
 */
import {classeDoTitulo} from "./ReferenceHome";

test("nome curto fica no tamanho cheio", () => {
  for (const nome of ["Push 1", "Upper C", "Pull", "Legs"]) {
    expect(classeDoTitulo(nome)).toBeUndefined();
  }
});

test("nome medio cede um degrau", () => {
  for (const nome of ["Upper Push A", "Full Body", "Peito e Ombro"]) {
    expect(classeDoTitulo(nome)).toBe("forge-nome-medio");
  }
  // "Costas 1" tem 8 caracteres e ainda cabe no tamanho cheio — o degrau comeca em 9.
  expect(classeDoTitulo("Costas 1")).toBeUndefined();
});

test("o nome que quebrou a tela do atleta cede dois degraus", () => {
  expect(classeDoTitulo("A · Quadríceps")).toBe("forge-nome-longo");
  expect(classeDoTitulo("B · Posterior e Glúteos")).toBe("forge-nome-longo");
  expect(classeDoTitulo("Escolha seu programa")).toBe("forge-nome-longo");
});

test("espaco em volta nao conta como comprimento", () => {
  // "  Push 1  " tem 10 caracteres, mas a pessoa le 6: o degrau segue o que aparece.
  expect(classeDoTitulo("  Push 1  ")).toBeUndefined();
});

test("ausencia de nome nao quebra nem inventa classe", () => {
  for (const vazio of [undefined, null, "", "   "]) {
    expect(classeDoTitulo(vazio)).toBeUndefined();
  }
});

test("o limiar e continuo: nao existe comprimento sem degrau definido", () => {
  // Varre de 1 a 40 caracteres e exige que todo tamanho caia em exatamente um degrau,
  // e que os degraus so cresçam. Um `if` invertido num refactor aparece aqui.
  const ordem = {undefined: 0, "forge-nome-medio": 1, "forge-nome-longo": 2};
  let anterior = 0;
  for (let n = 1; n <= 40; n += 1) {
    const grau = ordem[String(classeDoTitulo("x".repeat(n)))];
    expect(grau).toBeDefined();
    expect(grau).toBeGreaterThanOrEqual(anterior);
    anterior = grau;
  }
  expect(anterior).toBe(2);
});
