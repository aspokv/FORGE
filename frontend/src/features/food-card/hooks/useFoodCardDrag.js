import {useCallback, useRef, useState} from "react";
import {ALTURA, LARGURA, alturaDoCartao, prender} from "../lib/layout";
import {CARTAO} from "../lib/layout";

/**
 * Arrastar card e âncora, com ponteiro.
 *
 * `pointer*` e não `touch*`/`mouse*`: um conjunto de eventos só cobre dedo, mouse e
 * caneta, e `setPointerCapture` resolve o problema clássico do arrasto — o dedo sair de
 * cima do elemento no meio do movimento e o `move` parar de chegar.
 *
 * `touchAction: none` no elemento arrastável (no CSS) é o que impede a página de rolar
 * junto. Sem isso, arrastar um card para baixo rola o editor no celular e o card fica
 * para trás.
 *
 * A conversão de tela para peça é uma divisão pela escala do canvas. Como o canvas é
 * desenhado em 1080 x 1920 e encolhido por `transform`, um pixel de dedo vale
 * `1/escala` pixels lógicos — e nada mais precisa saber o tamanho da tela.
 */
export default function useFoodCardDrag({items, escalaRef, aoMover, aoSoltar}) {
  const [selecionado, setSelecionado] = useState(null);
  const [arrastando, setArrastando] = useState(false);
  const estado = useRef(null);

  const escala = () => escalaRef?.current || 1;

  const comecar = useCallback((evento, indice, alvo) => {
    evento.preventDefault();
    evento.stopPropagation();
    const item = items[indice];
    if (!item) return;
    try {
      evento.currentTarget.setPointerCapture?.(evento.pointerId);
    } catch {
      // Navegador sem captura de ponteiro: o arrasto ainda funciona enquanto o dedo
      // ficar sobre o elemento. Não vale derrubar a interação por causa disso.
    }
    const s = escala();
    estado.current = {
      indice, alvo, pointerId: evento.pointerId,
      // A diferença entre onde o dedo tocou e o canto do card. Sem guardar isto, o card
      // salta para ficar com o canto embaixo do dedo no primeiro movimento.
      deltaX: evento.clientX / s - (alvo === "card" ? item.cardX : item.anchorX) * LARGURA,
      deltaY: evento.clientY / s - (alvo === "card" ? item.cardY : item.anchorY) * ALTURA,
    };
    setSelecionado(indice);
    setArrastando(true);
  }, [items, escalaRef]);

  const noCard = useCallback((e, i) => comecar(e, i, "card"), [comecar]);
  const naAncora = useCallback((e, i) => comecar(e, i, "ancora"), [comecar]);

  const mover = useCallback(evento => {
    const atual = estado.current;
    if (!atual || evento.pointerId !== atual.pointerId) return;
    evento.preventDefault();
    const s = escala();
    const x = evento.clientX / s - atual.deltaX;
    const y = evento.clientY / s - atual.deltaY;
    const item = items[atual.indice];
    if (!item) return;

    if (atual.alvo === "card") {
      // O card é preso para não sair do quadro: metade de um card fora da peça é um
      // defeito que só aparece na exportação, quando já é tarde.
      aoMover(atual.indice, {
        cardX: prender(x / LARGURA, 0, (LARGURA - CARTAO.largura) / LARGURA),
        cardY: prender(y / ALTURA, 0, (ALTURA - alturaDoCartao(item)) / ALTURA),
      });
    } else {
      aoMover(atual.indice, {
        anchorX: prender(x / LARGURA), anchorY: prender(y / ALTURA),
      });
    }
  }, [items, escalaRef, aoMover]);

  const soltar = useCallback(evento => {
    const atual = estado.current;
    if (!atual || (evento && evento.pointerId !== atual.pointerId)) return;
    estado.current = null;
    setArrastando(false);
    if (aoSoltar) aoSoltar();
  }, [aoSoltar]);

  const limparSelecao = useCallback(() => {
    if (!estado.current) setSelecionado(null);
  }, []);

  return {
    selecionado, arrastando, noCard, naAncora, mover, soltar, limparSelecao,
    setSelecionado,
  };
}
