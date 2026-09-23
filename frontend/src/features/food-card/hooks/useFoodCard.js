import {useCallback, useEffect, useRef, useState} from "react";
import axios from "axios";
import {mensagemDeErro} from "../../mensagemDeErro";
import {ALTURA, LARGURA} from "../lib/layout";

/**
 * O estado do Food Card: carregar, mover, salvar e trocar a foto.
 *
 * Duas decisões de comportamento que valem explicar:
 *
 * **O movimento é local e a gravação é atrasada.** Arrastar um card dispara dezenas de
 * atualizações por segundo. Gravar cada uma encheria a rede e travaria o arrasto no
 * celular. Então o estado muda na hora, a tela responde na hora, e a gravação sai quando
 * o dedo solta — com um atraso curto, que junta ajustes seguidos num pedido só.
 *
 * **A foto é reduzida ANTES de subir.** Uma foto de câmera moderna tem 12 a 50 MP. Jogar
 * isso no DOM trava o editor no celular e estoura o limite de 8 MB do servidor. Como a
 * peça final tem 1920 px de altura, nada além disso acrescenta nitidez: reduzir para o
 * lado maior em 1920 é o ponto em que a qualidade para de importar e o peso para de
 * atrapalhar.
 */
const ATRASO_PARA_SALVAR = 700;
const MAIOR_LADO = Math.max(LARGURA, ALTURA);

export default function useFoodCard({API, cardId, axiosCliente = axios}) {
  const [card, setCard] = useState(null);
  const [estado, setEstado] = useState("carregando");
  const [erro, setErro] = useState("");
  const [salvando, setSalvando] = useState(false);
  const relogio = useRef(null);
  const pendente = useRef(null);

  const carregar = useCallback(async () => {
    if (!cardId) return;
    try {
      const r = await axiosCliente.get(`${API}/food-card/${cardId}`);
      setCard(r.data);
      setEstado("pronto");
    } catch (e) {
      setEstado("erro");
      setErro(mensagemDeErro(e, "Não foi possível abrir este Food Card."));
    }
  }, [API, axiosCliente, cardId]);

  /**
   * A foto não carregou. Busca um endereço novo, UMA vez.
   *
   * O endereço da foto é assinado e vale cinco minutos — escolha deliberada, porque
   * endereço de foto que dura horas vira link compartilhável sem querer. Montar um Food
   * Card leva mais que cinco minutos: escolher alimentos, arrastar cards, ajustar o
   * enquadramento. Quando o prazo vence, o `<img>` simplesmente falha, e antes disto a
   * tela não dizia nada: a peça ficava com o fundo vazio e nenhuma explicação. Foi assim
   * que o Nicolas importou uma foto e ficou sem saber se ela tinha subido.
   *
   * Uma vez só, e com trava: um endereço que falha por outro motivo — objeto que não
   * existe, armazenamento fora do ar — repetiria para sempre, e cada tentativa é uma
   * requisição.
   */
  const refazendo = useRef(false);
  const fotoFalhou = useCallback(async () => {
    if (refazendo.current) {
      setErro("A foto do prato não carregou. Toque em \"Escolher da galeria\" para enviar de novo.");
      return false;
    }
    refazendo.current = true;
    try {
      const r = await axiosCliente.get(`${API}/food-card/${cardId}`);
      const nova = r.data?.imageUrl;
      if (!nova) {
        setErro("A foto do prato não está mais disponível. Envie a foto de novo.");
        return false;
      }
      setCard(atual => (atual ? {...atual, imageUrl: nova} : atual));
      setErro("");
      return true;
    } catch (e) {
      setErro(mensagemDeErro(e, "A foto do prato não carregou."));
      return false;
    }
  }, [API, axiosCliente, cardId]);

  useEffect(() => { carregar(); }, [carregar]);
  useEffect(() => () => clearTimeout(relogio.current), []);

  const gravar = useCallback(async corpo => {
    if (!cardId) return;
    setSalvando(true);
    try {
      await axiosCliente.put(`${API}/food-card/${cardId}`, corpo);
      setErro("");
    } catch (e) {
      // O trabalho continua na tela. Perder o que o atleta acabou de posicionar por causa
      // de uma falha de rede seria pior do que o aviso.
      setErro(mensagemDeErro(e, "As mudanças não foram salvas ainda."));
    } finally {
      setSalvando(false);
    }
  }, [API, axiosCliente, cardId]);

  const agendar = useCallback(corpo => {
    pendente.current = {...(pendente.current || {}), ...corpo};
    clearTimeout(relogio.current);
    relogio.current = setTimeout(() => {
      const envio = pendente.current;
      pendente.current = null;
      if (envio) gravar(envio);
    }, ATRASO_PARA_SALVAR);
  }, [gravar]);

  /** Move um card ou um âncora. Só posição muda por aqui. */
  const mover = useCallback((indice, mudanca) => {
    setCard(atual => {
      if (!atual) return atual;
      const items = atual.items.map((item, i) => (i === indice ? {...item, ...mudanca} : item));
      return {...atual, items};
    });
  }, []);

  /** Chamado quando o dedo solta: é aqui que a gravação é marcada. */
  const confirmarMovimento = useCallback(() => {
    setCard(atual => {
      if (atual) {
        agendar({items: atual.items.map(i => ({
          cardX: i.cardX, cardY: i.cardY, anchorX: i.anchorX, anchorY: i.anchorY,
          primaryMacro: i.primaryMacro,
        }))});
      }
      return atual;
    });
  }, [agendar]);

  const ajustarFoto = useCallback(transform => {
    setCard(atual => (atual ? {...atual, imageTransform: transform} : atual));
    agendar({imageTransform: transform});
  }, [agendar]);

  const trocarMacro = useCallback((indice, macro) => {
    setCard(atual => {
      if (!atual) return atual;
      const items = atual.items.map((item, i) => (i === indice ? {...item, primaryMacro: macro} : item));
      agendar({items: items.map(i => ({
        cardX: i.cardX, cardY: i.cardY, anchorX: i.anchorX, anchorY: i.anchorY,
        primaryMacro: i.primaryMacro,
      }))});
      return {...atual, items};
    });
  }, [agendar]);

  const enviarFoto = useCallback(async arquivo => {
    setErro("");
    try {
      const reduzida = await reduzirFoto(arquivo);
      const corpo = new FormData();
      corpo.append("photo", reduzida, "prato.jpg");
      const r = await axiosCliente.post(`${API}/food-card/${cardId}/photo`, corpo,
                                        {headers: {"Content-Type": "multipart/form-data"}});
      refazendo.current = false;   // foto nova, chance nova de recuperacao
      setCard(atual => (atual ? {...atual, imageUrl: r.data.imageUrl,
                                 imageKey: r.data.imageKey} : atual));
      return true;
    } catch (e) {
      setErro(mensagemDeErro(e, "Não foi possível enviar essa foto."));
      return false;
    }
  }, [API, axiosCliente, cardId]);

  return {card, estado, erro, salvando, mover, confirmarMovimento, ajustarFoto,
          trocarMacro, enviarFoto, recarregar: carregar, fotoFalhou, setErro};
}

/**
 * Reduz a foto para o que a peça realmente usa.
 *
 * O lado maior vira 1920, que é a altura da peça: acima disso não existe nitidez que o
 * PNG final consiga mostrar, e abaixo disso a foto começa a aparecer borrada no Story.
 */
export async function reduzirFoto(arquivo, maiorLado = MAIOR_LADO) {
  const bitmap = await criarBitmap(arquivo);
  const proporcao = Math.min(1, maiorLado / Math.max(bitmap.width, bitmap.height));
  if (proporcao >= 1 && arquivo.size <= 4 * 1024 * 1024) return arquivo;

  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * proporcao);
  canvas.height = Math.round(bitmap.height * proporcao);
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close?.();

  return await new Promise(resolve => {
    canvas.toBlob(blob => resolve(blob || arquivo), "image/jpeg", 0.92);
  });
}

function criarBitmap(arquivo) {
  if (typeof createImageBitmap === "function") return createImageBitmap(arquivo);
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(arquivo);
    const img = new Image();
    img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("Foto inválida.")); };
    img.src = url;
  });
}
