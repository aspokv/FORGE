import telaInicio from "../../assets/forge-tela-inicio.webp";
import telaTreino from "../../assets/forge-tela-treino.webp";
import telaNutricao from "../../assets/forge-tela-nutricao.webp";
import telaProgresso from "../../assets/forge-tela-progresso.webp";

export const PHONE_SCREENS = [telaInicio, telaTreino, telaNutricao, telaProgresso];

export const CINEMATIC_CHAPTERS = [
  {
    eyebrow: "FORGE / PERFORMANCE OS",
    title: <>Um programa.<br /><em>O seu perfil.</em></>,
    text: "Treino e alimentação construídos em torno do seu corpo, da sua rotina e do seu histórico.",
  },
  {
    eyebrow: "01 / TREINO",
    title: <>A sessão certa.<br /><em>No dia certo.</em></>,
    text: "Divisão, exercícios, séries e intensidade organizados para você entrar e executar.",
  },
  {
    eyebrow: "02 / NUTRIÇÃO",
    title: <>Seu plano acompanha<br /><em>a vida real.</em></>,
    text: "Metas, refeições e substituições coerentes com o objetivo — sem perder o controle do dia.",
  },
  {
    eyebrow: "03 / EVOLUÇÃO",
    title: <>Cada registro decide<br /><em>o próximo passo.</em></>,
    text: "O FORGE conecta treino, alimentação e recuperação para transformar histórico em progressão.",
  },
];

export const chapterFromProgress = (value) => {
  if (value < 0.23) return 0;
  if (value < 0.46) return 1;
  if (value < 0.7) return 2;
  return 3;
};
