/**
 * Compressao no cliente, antes do upload.
 *
 * Foto de celular hoje sai com 3 a 8 MB. O que a analise precisa cabe em muito menos, e o
 * excesso e pago em dados moveis por quem esta enviando. Reduzir aqui e a unica forma de
 * economizar isso — comprimir no servidor ja seria depois de o dado ter trafegado.
 *
 * Sai sempre JPEG. Isso resolve o HEIC do iPhone de graca: o `createImageBitmap` decodifica
 * o que o navegador souber abrir, e o que sai do canvas e JPEG independentemente do que
 * entrou. Nenhuma biblioteca de conversao envolvida.
 */

/** Maior lado da imagem final. Acima disso nao ha ganho visivel para a leitura. */
const MAIOR_LADO = 1600;
const QUALIDADE = 0.82;

/** O tamanho que ainda vale a pena aceitar depois de comprimir. */
const TETO = 8 * 1024 * 1024;

function medidasReduzidas(largura, altura) {
  const maior = Math.max(largura, altura);
  if (maior <= MAIOR_LADO) return { largura, altura };
  const fator = MAIOR_LADO / maior;
  return {
    largura: Math.round(largura * fator),
    altura: Math.round(altura * fator),
  };
}

/**
 * Reduz e recodifica a imagem. Devolve um File novo.
 *
 * Se o navegador nao souber decodificar (HEIC em navegador antigo, por exemplo), o arquivo
 * original e devolvido: melhor tentar enviar e deixar o servidor recusar com uma mensagem
 * clara do que travar a tela aqui com um erro que a pessoa nao sabe resolver.
 */
export async function comprimirImagem(arquivo) {
  if (typeof createImageBitmap !== "function" || typeof document === "undefined") {
    return arquivo;
  }

  let bitmap;
  try {
    bitmap = await createImageBitmap(arquivo);
  } catch {
    return arquivo;
  }

  try {
    const { largura, altura } = medidasReduzidas(bitmap.width, bitmap.height);
    const tela = document.createElement("canvas");
    tela.width = largura;
    tela.height = altura;
    const ctx = tela.getContext("2d");
    if (!ctx) return arquivo;
    ctx.drawImage(bitmap, 0, 0, largura, altura);

    const blob = await new Promise((ok) => tela.toBlob(ok, "image/jpeg", QUALIDADE));
    if (!blob || blob.size > TETO) return arquivo;

    // Comprimir e devolver algo MAIOR seria trabalho para piorar: acontece com imagem ja
    // pequena e muito otimizada.
    if (blob.size >= arquivo.size && bitmap.width <= MAIOR_LADO) return arquivo;

    const nome = String(arquivo.name || "foto").replace(/\.[^.]+$/, "") + ".jpg";
    return new File([blob], nome, { type: "image/jpeg", lastModified: Date.now() });
  } finally {
    bitmap.close?.();
  }
}
