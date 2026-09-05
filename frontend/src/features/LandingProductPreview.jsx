import telaTreino from "../assets/forge-tela-treino.webp";
import telaNutricao from "../assets/forge-tela-nutricao.webp";
import telaProgresso from "../assets/forge-tela-progresso.webp";

/**
 * A composicao do hero: tres telas reais do FORGE, em profundidade.
 *
 * Treino ao centro, nutricao e progresso recuadas de cada lado. E a promessa da pagina
 * dita em uma imagem — o FORGE junta as tres coisas — antes de o storytelling abaixo
 * separar cada uma e explicar.
 *
 * A tela inicial NAO entra aqui de proposito: ela aparece sozinha mais abaixo, e repetir
 * a mesma imagem gastaria a novidade da segunda aparicao.
 *
 * A imagem e SO a tela; o aparelho e desenhado pelo CSS (`.lp-fone`). Antes, o arquivo
 * trazia a moldura junto e, sendo retangular, formava uma caixa preta por cima do cenario
 * da landing — de canto vivo, e com escala diferente entre um arquivo e outro. Com a
 * moldura no layout, o recorte e a mesma forma arredondada para todas, e o enquadramento
 * nao depende de como cada arquivo foi cortado.
 */

const TELAS = [
  {
    id: "esquerda",
    src: telaNutricao,
    alt: "Tela de nutrição do FORGE, com as refeições do dia e as calorias de cada uma.",
  },
  {
    id: "direita",
    src: telaProgresso,
    alt: "Tela de progresso do FORGE, com os melhores resultados e a evolução de carga.",
  },
  {
    id: "centro",
    src: telaTreino,
    alt: "Tela de treino do FORGE: Upper 1, 60 minutos, com a lista de exercícios e séries.",
  },
];

export default function LandingProductPreview() {
  return (
    <figure className="lp-composicao" aria-labelledby="lp-composicao-legenda">
      <div className="lp-palco">
        {TELAS.map((t) => (
          <div key={t.id} className={`lp-fone lp-fone-${t.id}`}>
            <img
              className="lp-fone-tela"
              src={t.src}
              alt={t.alt}
              width="648"
              height="1404"
              loading="eager"
              decoding="async"
            />
          </div>
        ))}
      </div>
      <figcaption id="lp-composicao-legenda">
        Treino, nutrição e progresso no mesmo sistema
      </figcaption>
    </figure>
  );
}
