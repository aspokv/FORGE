import {useEffect, useRef, useState} from "react";
import {ALTURA, LARGURA, MARCA, TIPO, escalaQueCabe} from "../lib/layout";
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
  modoPreview = false, escalaRef, onFotoFalhou, reserva = null,
}) {
  const molduraRef = useRef(null);
  const [escala, setEscala] = useState(0.3);
  // Conta as tentativas de carregar a foto, e serve de `key` da <img>.
  //
  // Sem isto a recuperacao nao funciona: pedir um endereco novo devolve a MESMA string
  // quando a assinatura e gerada no mesmo segundo, e o navegador nao repete requisicao
  // para um `src` que nao mudou. Trocar a `key` monta um elemento novo, que pede de novo.
  //
  // So sobe quando a recuperacao diz que vale a pena tentar: se subisse a cada `onError`,
  // um endereco que falha sempre entraria em laco infinito de requisicoes.
  const [tentativa, setTentativa] = useState(0);
  // Quando o endereço assinado falha e existe a cópia local desta sessão, mostra a cópia.
  // Melhor a foto certa vinda da memória do que um retângulo preto com uma explicação.
  const [usandoReserva, setUsandoReserva] = useState(false);
  const mostrada = usandoReserva && reserva ? reserva : imagem;

  // A escala acompanha o contêiner real. `ResizeObserver` em vez de um evento de janela
  // porque o editor tem barras que abrem e fecham sem a janela mudar de tamanho.
  //
  // Mede as DUAS dimensões, e não só a largura. A peça é 9:16; medindo só a largura, num
  // celular de 412px ela reivindicava 733px de altura e empurrava as abas e o painel de
  // controles para fora da tela — em navegador de celular, com barra de endereço, sobram
  // por volta de 680px, e o painel inteiro ficava invisível sem nenhum indício. Foi assim
  // que o botão de escolher a foto da galeria sumiu para quem estava usando.
  useEffect(() => {
    const alvo = molduraRef.current;
    if (!alvo) return undefined;
    // Mede o ESPACO DISPONIVEL (o pai), e nao a propria moldura: medir a si mesma criaria
    // um laco, porque e a medida que define o tamanho dela.
    const espaco = alvo.parentElement;
    const medir = () => {
      const nova = escalaQueCabe(espaco?.clientWidth || alvo.clientWidth,
                                 espaco?.clientHeight);
      setEscala(nova);
      if (escalaRef) escalaRef.current = nova;
    };
    medir();
    if (typeof ResizeObserver === "undefined") return undefined;
    const observador = new ResizeObserver(medir);
    observador.observe(espaco || alvo);
    return () => observador.disconnect();
  }, [escalaRef]);

  const t = imageTransform || {scale: 1, offsetX: 0, offsetY: 0};

  // Largura e altura saem da escala ja calculada, e nao de `aspect-ratio` com
  // `max-height`: aquela combinacao encolhia so a altura e achatava a peca — medido em
  // 412x680, saia 380x278, proporcao 1.37 onde o certo e 0.563. Aqui as duas dimensoes
  // vem do mesmo numero, entao a proporcao nao tem como divergir.
  return (
    <div className="fc-moldura" ref={molduraRef} data-testid="fc-moldura"
         style={{width: LARGURA * escala, height: ALTURA * escala}}>
      <div className="fc-canvas" data-testid="fc-canvas"
           style={{
             width: LARGURA, height: ALTURA,
             transform: `scale(${escala})`, transformOrigin: "top left",
           }}
           onPointerDown={onFundoPressionado}>

        {/* Camada 1: a foto do atleta, intocada. Só enquadramento muda. */}
        <div className="fc-foto" data-testid="fc-foto">
          {mostrada ? (
            /* `onError` nao e enfeite: o endereco da foto e assinado e vale cinco minutos,
               e montar uma peca leva mais que isso. Sem este aviso o `<img>` falha calado,
               a peca fica com o fundo vazio e nada na tela explica por que. */
            <img key={`${mostrada}#${tentativa}`} src={mostrada} alt="" draggable="false"
                 data-testid="fc-foto-img"
                 data-fonte={usandoReserva && reserva ? "reserva" : "servidor"}
                 onError={async () => {
                   // A reserva primeiro: ela não depende de rede nem de assinatura, então
                   // resolve na hora. Só quando não há reserva vale gastar uma ida ao
                   // servidor atrás de um endereço novo.
                   if (reserva && !usandoReserva) { setUsandoReserva(true); return; }
                   if (await onFotoFalhou?.()) setTentativa(n => n + 1);
                 }} style={{
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
