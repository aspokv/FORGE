/**
 * Objetivos do onboarding: rotulo do usuario x valor persistido.
 *
 * Os termos tecnicos ("Hipertrofia", "Recomposição", "Performance", "Especialização")
 * confundem quem esta comecando, mas sao os valores que ja estao gravados no banco dos
 * atletas atuais. Entao a mudanca e so de APRESENTACAO: o `v` continua sendo exatamente
 * o que vai para o backend, e nenhum valor novo foi inventado.
 *
 * Mora fora do App.js para poder ser testado com o Jest que ja vem no react-scripts,
 * sem instalar biblioteca de renderizacao.
 */

export const GOALS = [
  { v: "Hipertrofia", l: "Ganhar massa muscular",
    d: "Aumente massa muscular, força e volume corporal." },
  { v: "Recomposição", l: "Emagrecer e definir",
    d: "Reduza gordura preservando o máximo possível de massa muscular." },
  { v: "Performance", l: "Melhorar desempenho",
    d: "Desenvolva força, resistência e capacidade esportiva." },
  { v: "Especialização", l: "Priorizar uma região",
    d: "Dê mais volume e frequência às regiões que você deseja desenvolver." },
];

/** O unico objetivo que revela a intensidade de emagrecimento. */
export const FAT_LOSS_GOAL = "Recomposição";

/**
 * Intensidade que deve ser enviada ao backend.
 *
 * Trocar de objetivo nao pode carregar uma intensidade incompativel: fora do
 * emagrecimento ela nao significa nada, e mandar "agressivo" junto de "Hipertrofia"
 * deixaria onboarding e Alimentacao discordando. null = nada escolhido, e o backend
 * mantem o comportamento padrao dele.
 */
export function cutIntensityForSubmit(goal, intensity) {
  if (goal !== FAT_LOSS_GOAL) return null;
  return intensity || null;
}
