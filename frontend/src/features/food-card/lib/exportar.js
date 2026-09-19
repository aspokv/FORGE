/**
 * Exportação do Forge Food Card: PNG 1080 x 1920, desenhado em canvas.
 *
 * Por que canvas, e não uma captura do DOM
 * ----------------------------------------
 * Capturar o DOM entrega a peça na resolução do APARELHO. Num celular comum, a prévia tem
 * uns 360 px de largura: o PNG sairia com 360 px e subiria borrado para o Story. Ampliar
 * depois não devolve nitidez que nunca existiu.
 *
 * Aqui o canvas nasce com 1080 x 1920 e tudo é desenhado nesse tamanho, lendo as MESMAS
 * constantes de `layout.js` que a prévia usa. A prévia é esse mesmo layout encolhido por
 * `transform: scale()`, então as duas têm a mesma composição por construção, e não por
 * coincidência mantida à mão.
 *
 * Zero dependência nova. `html2canvas`, `dom-to-image` e `satori` resolveriam parte disto
 * e custariam entre 200 KB e 1 MB no pacote, mais a captura na resolução errada no caso
 * das duas primeiras.
 *
 * Onde a fidelidade tem limite, declarado
 * ---------------------------------------
 * 1. `letterSpacing` de canvas existe no Chrome 99+ e no Safari 17.4+. Em navegador mais
 *    antigo o espaçamento das etiquetas sai menor; o resto da composição não muda.
 * 2. O desfoque atrás dos cards é reproduzido desenhando a região borrada da foto sob
 *    cada card. É o mesmo efeito do `backdrop-filter` da prévia, calculado de outro jeito.
 */
import {
  ALTURA, CARTAO, CONECTOR, CORES, FONTE, LARGURA, MARCA, RESUMO, TIPO,
  alturaDoCartao, caixaDoCartao, saidaDoConector,
} from "./layout";
import {ROTULO_DO_MACRO, descricaoDe, quantidadeDe, valorDoMacro} from "./conteudo";
import {QUADRO, caminhosDoAlimento, caminhosDoMacro} from "./icones";

const COLUNAS_DO_RESUMO = [
  {chave: "protein", rotulo: "PROTEÍNA", unidade: "g"},
  {chave: "carbs", rotulo: "CARBOIDRATOS", unidade: "g"},
  {chave: "fat", rotulo: "GORDURA", unidade: "g"},
  {chave: "calories", rotulo: "ENERGIA", unidade: "kcal"},
];

/** Desenha a peça inteira e devolve um Blob PNG de 1080 x 1920. */
export async function exportarFoodCard({imagem, imageTransform, items = [], summary}) {
  const canvas = document.createElement("canvas");
  canvas.width = LARGURA;
  canvas.height = ALTURA;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Este navegador não conseguiu preparar a imagem.");

  const foto = imagem ? await carregarImagem(imagem) : null;

  desenharFundo(ctx, foto, imageTransform);
  const borrada = foto ? fotoBorrada(foto, imageTransform) : null;
  desenharVeu(ctx);
  desenharMarca(ctx);
  items.forEach(item => desenharConector(ctx, item));
  items.forEach(item => desenharCartao(ctx, item, borrada));
  desenharResumo(ctx, summary, borrada);

  return await new Promise((resolve, reject) => {
    canvas.toBlob(
      blob => (blob ? resolve(blob) : reject(new Error("Não foi possível gerar a imagem."))),
      "image/png",
    );
  });
}

/**
 * Carrega a foto sem sujar o canvas.
 *
 * `crossOrigin` antes do `src` é obrigatório: definido depois, o navegador já começou a
 * requisição sem o cabeçalho e o canvas fica marcado como contaminado — aí `toBlob`
 * estoura uma exceção de segurança e a exportação morre no fim, depois de tudo pronto.
 */
export function carregarImagem(fonte) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    if (!String(fonte).startsWith("data:")) img.crossOrigin = "anonymous";
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("Não foi possível carregar a foto."));
    img.src = fonte;
  });
}

/** A foto cobrindo o quadro, sem deformar, com o zoom e o deslocamento do atleta. */
function desenharFundo(ctx, foto, transform) {
  ctx.fillStyle = "#08090a";
  ctx.fillRect(0, 0, LARGURA, ALTURA);
  if (!foto) return;
  const t = {scale: 1, offsetX: 0, offsetY: 0, ...(transform || {})};
  const proporcao = Math.max(LARGURA / foto.width, ALTURA / foto.height) * t.scale;
  const largura = foto.width * proporcao;
  const altura = foto.height * proporcao;
  ctx.drawImage(
    foto,
    (LARGURA - largura) / 2 + t.offsetX * LARGURA,
    (ALTURA - altura) / 2 + t.offsetY * ALTURA,
    largura, altura,
  );
}

/** A mesma foto, borrada, para servir de fundo aos cards translúcidos. */
function fotoBorrada(foto, transform) {
  const canvas = document.createElement("canvas");
  canvas.width = LARGURA;
  canvas.height = ALTURA;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  // `filter` de canvas não existe em toda versão. Sem ele, o card fica só com o preto
  // translúcido, que é legível — só perde o desfoque.
  if ("filter" in ctx) ctx.filter = "blur(18px)";
  desenharFundo(ctx, foto, transform);
  return canvas;
}

/** Escurecimento sutil no topo e na base, para o texto branco ter contraste. */
function desenharVeu(ctx) {
  const topo = ctx.createLinearGradient(0, 0, 0, ALTURA * 0.3);
  topo.addColorStop(0, "rgba(0,0,0,0.58)");
  topo.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = topo;
  ctx.fillRect(0, 0, LARGURA, ALTURA * 0.3);

  const base = ctx.createLinearGradient(0, ALTURA * 0.72, 0, ALTURA);
  base.addColorStop(0, "rgba(0,0,0,0)");
  base.addColorStop(1, "rgba(0,0,0,0.62)");
  ctx.fillStyle = base;
  ctx.fillRect(0, ALTURA * 0.72, LARGURA, ALTURA * 0.28);
}

function desenharMarca(ctx) {
  aplicarFonte(ctx, TIPO.marca);
  ctx.fillStyle = CORES.texto;
  ctx.textBaseline = "alphabetic";
  ctx.fillText("FORGE", MARCA.x, MARCA.y + TIPO.marca.tamanho);

  aplicarFonte(ctx, TIPO.assinatura);
  ctx.fillStyle = CORES.textoFraco;
  MARCA.assinatura.forEach((linha, i) => {
    ctx.fillText(linha, MARCA.x, MARCA.assinaturaY + TIPO.assinatura.tamanho
      + i * MARCA.entrelinhaDaAssinatura);
  });
}

function desenharConector(ctx, item) {
  const ancora = {x: item.anchorX * LARGURA, y: item.anchorY * ALTURA};
  const saida = saidaDoConector(caixaDoCartao(item), ancora);

  ctx.strokeStyle = CORES.linha;
  ctx.lineWidth = CONECTOR.traco;
  ctx.lineCap = "round";
  ctx.beginPath();
  ctx.moveTo(saida.x, saida.y);
  ctx.lineTo(ancora.x, ancora.y);
  ctx.stroke();

  ctx.beginPath();
  ctx.arc(ancora.x, ancora.y, CONECTOR.raioDoPonto, 0, Math.PI * 2);
  ctx.fillStyle = CORES.linha;
  ctx.fill();
  ctx.strokeStyle = "rgba(0,0,0,0.35)";
  ctx.lineWidth = 1.5;
  ctx.stroke();
}

function desenharCartao(ctx, item, borrada) {
  const caixa = caixaDoCartao(item);
  vidro(ctx, caixa.x, caixa.y, caixa.largura, caixa.altura, CARTAO.raio, borrada);

  const esquerda = caixa.x + CARTAO.padding;
  const textoX = esquerda + CARTAO.icone.tamanho + CARTAO.espacoDepoisDoIcone;
  const larguraDoTexto = caixa.largura - CARTAO.padding * 2
    - CARTAO.icone.tamanho - CARTAO.espacoDepoisDoIcone;

  // O círculo do ícone do alimento.
  const centroDoIcone = {
    x: esquerda + CARTAO.icone.raio,
    y: caixa.y + CARTAO.padding + CARTAO.icone.raio,
  };
  ctx.beginPath();
  ctx.arc(centroDoIcone.x, centroDoIcone.y, CARTAO.icone.raio, 0, Math.PI * 2);
  ctx.strokeStyle = CORES.vidroBorda;
  ctx.lineWidth = CARTAO.icone.traco;
  ctx.stroke();
  desenharIcone(ctx, caminhosDoAlimento(item.iconKey), centroDoIcone,
                CARTAO.icone.tamanho * 0.56, CARTAO.icone.traco);

  let y = caixa.y + CARTAO.padding;

  aplicarFonte(ctx, TIPO.nomeDoAlimento);
  ctx.fillStyle = CORES.texto;
  y += TIPO.nomeDoAlimento.tamanho;
  ctx.fillText(String(item.name || "").toUpperCase(), textoX, y, larguraDoTexto);

  aplicarFonte(ctx, TIPO.quantidade);
  y += 12 + TIPO.quantidade.tamanho;
  ctx.fillText(quantidadeDe(item), textoX, y);

  const descricao = descricaoDe(item);
  if (descricao) {
    aplicarFonte(ctx, TIPO.descricao);
    ctx.fillStyle = CORES.textoFraco;
    y += 14;
    for (const linha of quebrar(ctx, descricao, larguraDoTexto).slice(0, 2)) {
      y += TIPO.descricao.entrelinha;
      ctx.fillText(linha, textoX, y);
    }
  }

  // O divisor e o bloco do macro.
  const divisorY = caixa.y + caixa.altura - CARTAO.alturaDoBlocoDoMacro - CARTAO.padding;
  ctx.strokeStyle = CORES.divisor;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(esquerda, divisorY);
  ctx.lineTo(caixa.x + caixa.largura - CARTAO.padding, divisorY);
  ctx.stroke();

  const macroY = divisorY + CARTAO.alturaDoBlocoDoMacro / 2;
  desenharIcone(ctx, caminhosDoMacro(item.primaryMacro),
                {x: esquerda + 22, y: macroY}, 40, 1.7);

  const macroX = esquerda + 62;
  aplicarFonte(ctx, TIPO.rotuloDoMacro);
  ctx.fillStyle = CORES.textoFraco;
  ctx.fillText(ROTULO_DO_MACRO[item.primaryMacro] || ROTULO_DO_MACRO.protein,
               macroX, macroY - 16);

  aplicarFonte(ctx, TIPO.valorDoMacro);
  ctx.fillStyle = CORES.texto;
  ctx.fillText(`${valorDoMacro(item)} g`, macroX, macroY + 20);

  aplicarFonte(ctx, TIPO.porcao);
  ctx.fillStyle = CORES.textoMuitoFraco;
  ctx.fillText("por porção", macroX, macroY + 42);
}

function desenharResumo(ctx, summary, borrada) {
  const total = summary || {};
  const x = RESUMO.margem;
  const largura = LARGURA - RESUMO.margem * 2;
  const y = ALTURA - RESUMO.distanciaDaBase - RESUMO.alturaDoBloco;
  vidro(ctx, x, y, largura, RESUMO.alturaDoBloco, RESUMO.raio, borrada);

  const coluna = largura / COLUNAS_DO_RESUMO.length;
  COLUNAS_DO_RESUMO.forEach((item, i) => {
    const centro = x + coluna * i;
    if (i) {
      ctx.strokeStyle = CORES.divisor;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(centro, y + 26);
      ctx.lineTo(centro, y + RESUMO.alturaDoBloco - 26);
      ctx.stroke();
    }
    desenharIcone(ctx, caminhosDoMacro(item.chave),
                  {x: centro + 40, y: y + RESUMO.alturaDoBloco / 2}, RESUMO.icone, 1.7);

    const textoX = centro + 72;
    aplicarFonte(ctx, TIPO.rotuloDoResumo);
    ctx.fillStyle = CORES.textoFraco;
    ctx.fillText(item.rotulo, textoX, y + RESUMO.alturaDoBloco / 2 - 8);

    aplicarFonte(ctx, TIPO.valorDoResumo);
    ctx.fillStyle = CORES.texto;
    ctx.fillText(`${Math.round(Number(total[item.chave] || 0))} ${item.unidade}`,
                 textoX, y + RESUMO.alturaDoBloco / 2 + 26);
  });
}

/** Retângulo de vidro: a foto borrada recortada, mais preto translúcido, mais borda. */
function vidro(ctx, x, y, largura, altura, raio, borrada) {
  ctx.save();
  caminhoArredondado(ctx, x, y, largura, altura, raio);
  ctx.clip();
  if (borrada) ctx.drawImage(borrada, 0, 0);
  ctx.fillStyle = CORES.vidro;
  ctx.fillRect(x, y, largura, altura);
  ctx.restore();

  caminhoArredondado(ctx, x, y, largura, altura, raio);
  ctx.strokeStyle = CORES.vidroBorda;
  ctx.lineWidth = 1.5;
  ctx.stroke();
}

function caminhoArredondado(ctx, x, y, largura, altura, raio) {
  const r = Math.min(raio, largura / 2, altura / 2);
  ctx.beginPath();
  if (ctx.roundRect) {
    ctx.roundRect(x, y, largura, altura, r);
    return;
  }
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + largura, y, x + largura, y + altura, r);
  ctx.arcTo(x + largura, y + altura, x, y + altura, r);
  ctx.arcTo(x, y + altura, x, y, r);
  ctx.arcTo(x, y, x + largura, y, r);
  ctx.closePath();
}

/** Um ícone do catálogo, centrado num ponto, no tamanho pedido. */
function desenharIcone(ctx, caminhos, centro, tamanho, traco) {
  if (typeof Path2D === "undefined") return;
  const fator = tamanho / QUADRO;
  ctx.save();
  ctx.translate(centro.x - tamanho / 2, centro.y - tamanho / 2);
  ctx.scale(fator, fator);
  ctx.strokeStyle = CORES.texto;
  ctx.lineWidth = traco / fator;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  for (const d of caminhos) ctx.stroke(new Path2D(d));
  ctx.restore();
}

function aplicarFonte(ctx, tipo) {
  ctx.font = `${tipo.peso} ${tipo.tamanho}px ${FONTE}`;
  ctx.textBaseline = "alphabetic";
  // Propriedade recente: onde não existe, a atribuição é ignorada em silêncio e o texto
  // sai com espaçamento normal.
  if ("letterSpacing" in ctx) ctx.letterSpacing = `${tipo.espaco || 0}px`;
}

function quebrar(ctx, texto, largura) {
  const palavras = String(texto).split(" ");
  const linhas = [];
  let atual = "";
  for (const palavra of palavras) {
    const teste = atual ? `${atual} ${palavra}` : palavra;
    if (ctx.measureText(teste).width > largura && atual) {
      linhas.push(atual);
      atual = palavra;
    } else {
      atual = teste;
    }
  }
  if (atual) linhas.push(atual);
  return linhas;
}

/** O nome sugerido do arquivo, com carimbo de tempo para não sobrescrever o anterior. */
export function nomeDoArquivo() {
  const agora = new Date();
  const carimbo = agora.toISOString().slice(0, 19).replace(/[:T]/g, "-");
  return `forge-food-card-${carimbo}.png`;
}
