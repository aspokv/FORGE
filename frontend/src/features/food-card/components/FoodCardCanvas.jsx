import {useEffect, useRef, useState} from "react";
import {ALTURA, LARGURA, MARCA, TIPO} from "../lib/layout";
import FoodCalloutCard from "./FoodCalloutCard";
import FoodConnector from "./FoodConnector";
import MacroSummary from "./MacroSummary";

/**
 * O canvas 9:16 da peça.
 *
 * O truque que faz tudo funcionar: o conteúdo é desenhado em 1080 x 1920 DE VERDADE e o
 * bloco inteiro é encolhido por `transform: scale()` até caber na largura disponível.
 * Não é um layout parecido em escala menor — é o mesmo layout, com os mesmos números,
 * visto de longe.
 *
 * Isso resolve de uma vez três coisas que costumam divergir:
 *
 *   a prévia no celular, a prévia no desktop e a exportação em 1080 x 1920 têm a MESMA
 *   composição, porque nenhuma delas tem medidas próprias;
 *
 *   o arrasto converte pixel de tela para pixel lógico dividindo pela escala, uma conta
 *   só, em vez de um sistema de coordenadas por tamanho de tela;
 *
 *   a foto é posicionada uma vez e vale para as três.
 */
export default function FoodCardCanvas({
  imagem, imageTransform, items = [], summary, selecionado = null,
  onPointerDownCard, onPointerDownAncora, onFundoPressionado,
  modoPreview = false, escalaRef,
}) {
  const molduraRef = useRef(null);
  const [escala, setEscala] = useState(0.3);

  // A escala acompanha a largura real do contêiner. `ResizeObserver` em vez de um evento
  // de janela porque o editor tem barras que abrem e fecham sem a janela mudar de tamanho.
  useEffect(() => {
    const alvo = molduraRef.current;
    if (!alvo) return undefined;
    const medir = () => {
      const largura = alvo.clientWidth || LARGURA;
      const nova = largura / LARGURA;
      setEscala(nova);
      if (escalaRef) escalaRef.current = nova;
    };
    medir();
    if (typeof ResizeObserver === "undefined") return undefined;
    const observador = new ResizeObserver(medir);
    observador.observe(alvo);
    return () => observador.disconnect();
  }, [escalaRef]);

  const t = imageTransform || {scale: 1, offsetX: 0, offsetY: 0};

  return (
    <div className="fc-moldura" ref={molduraRef} data-testid="fc-moldura"
         style={{aspectRatio: `${LARGURA} / ${ALTURA}`}}>
      <div className="fc-canvas" data-testid="fc-canvas"
           style={{
             width: LARGURA, height: ALTURA,
             transform: `scale(${escala})`, transformOrigin: "top left",
           }}
           onPointerDown={onFundoPressionado}>

        {/* Camada 1: a foto do atleta, intocada. Só enquadramento muda. */}
        <div className="fc-foto" data-testid="fc-foto">
          {imagem ? (
            <img src={imagem} alt="" draggable="false" style={{
              transform: `translate(${t.offsetX * LARGURA}px, ${t.offsetY * ALTURA}px) scale(${t.scale})`,
            }} />
          ) : (
            <div className="fc-foto-vazia" data-testid="fc-foto-vazia">
              <span>Adicione a foto do prato</span>
            </div>
          )}
        </div>

        {/* Camada 2: escurecimento sutil no topo e na base, para o texto branco ter
            contraste sem precisar de sombra dura em cada peça de texto. */}
        <div className="fc-veu" aria-hidden="true" />

        {/* Camada 3: a marca. Fixa, e o atleta não move nem remove na V1. */}
        <div className="fc-marca" style={{left: MARCA.x, top: MARCA.y}}>
          <span className="fc-marca-nome" style={{
            fontSize: TIPO.marca.tamanho, fontWeight: TIPO.marca.peso,
            letterSpacing: TIPO.marca.espaco,
          }}>FORGE</span>
          <span className="fc-marca-assinatura" style={{
            fontSize: TIPO.assinatura.tamanho, fontWeight: TIPO.assinatura.peso,
            letterSpacing: TIPO.assinatura.espaco,
            lineHeight: `${MARCA.entrelinhaDaAssinatura}px`,
          }}>
            {MARCA.assinatura.map(linha => <span key={linha}>{linha}</span>)}
          </span>
        </div>

        {/* Camada 4: conectores, abaixo dos cards para a linha entrar por baixo deles. */}
        <FoodConnector itens={items} selecionado={selecionado}
                       onPointerDownAncora={modoPreview ? undefined : onPointerDownAncora} />

        {/* Camada 5: os cards. */}
        {items.map((item, i) => (
          <FoodCalloutCard
            key={item.foodId || i} item={item} indice={i}
            selecionado={!modoPreview && selecionado === i}
            onPointerDown={modoPreview ? undefined : e => onPointerDownCard(e, i)} />
        ))}

        {/* Camada 6: o resumo da refeição completa. */}
        <MacroSummary summary={summary} />
      </div>
    </div>
  );
}
