import telaTreino from "../assets/forge-tela-treino.webp";
import telaNutricao from "../assets/forge-tela-nutricao.webp";
import telaProgresso from "../assets/forge-tela-progresso.webp";

/**
 * A composicao do hero: tres telas reais do FORGE, em profundidade.
 *
 * Treino no centro, nutricao e progresso recuadas de cada lado. E a promessa da pagina
 * dita em uma imagem — o FORGE junta as tres coisas — antes de o storytelling abaixo
 * separar cada uma e explicar.
 *
 * A tela inicial NAO entra aqui de proposito: ela aparece sozinha mais abaixo, e repetir
 * a mesma imagem duas vezes gastaria a novidade da segunda aparicao.
 *
 * Sao capturas reais, nao uma maquete montada em HTML. A versao anterior desta pagina
 * remontava a Home em marcacao com numeros ilustrativos ("1.420 / 2.400 kcal"), o que
 * obrigava a legenda "Dados ilustrativos" e ainda assim mostrava uma interface que nao
 * existia. Imagem real nao precisa de ressalva e nao pode divergir do produto.
 */
export default function LandingProductPreview() {
  return (
    <figure className="lp-composicao" aria-labelledby="lp-composicao-legenda">
      <div className="lp-palco">
        <img
          className="lp-tela lp-tela-esquerda"
          src={telaNutricao}
          alt="Tela de nutrição do FORGE, com as refeições do dia e as calorias de cada uma."
          width="504"
          height="1168"
          loading="eager"
          decoding="async"
        />
        <img
          className="lp-tela lp-tela-direita"
          src={telaProgresso}
          alt="Tela de progresso do FORGE, com a carga por semana e o mapa de estímulo."
          width="504"
          height="1168"
          loading="eager"
          decoding="async"
        />
        <img
          className="lp-tela lp-tela-centro"
          src={telaTreino}
          alt="Tela de treino do FORGE: peitoral e ombros, 60 minutos, com a lista de exercícios e séries."
          width="504"
          height="1168"
          loading="eager"
          decoding="async"
        />
      </div>
      <figcaption id="lp-composicao-legenda">
        Treino, nutrição e progresso no mesmo sistema
      </figcaption>
    </figure>
  );
}
