import { comprimirImagem } from "./comprimirImagem";

/**
 * A compressao roda no navegador, com canvas e createImageBitmap. No jsdom nenhum dos dois
 * existe de verdade — e e justamente esse o caso que precisa estar coberto: quando o
 * ambiente nao sabe decodificar a imagem, o arquivo original tem de seguir em frente. O
 * contrario travaria o envio de quem esta num navegador antigo, ou com HEIC que o
 * navegador nao abre, com um erro que a pessoa nao tem como resolver.
 */

const arquivo = (nome = "foto.heic", tipo = "image/heic", tamanho = 2048) =>
  new File([new Uint8Array(tamanho)], nome, { type: tipo });

describe("quando o navegador nao consegue decodificar", () => {
  const original = global.createImageBitmap;

  afterEach(() => {
    global.createImageBitmap = original;
  });

  test("sem createImageBitmap, devolve o arquivo original", async () => {
    global.createImageBitmap = undefined;
    const entrada = arquivo();
    await expect(comprimirImagem(entrada)).resolves.toBe(entrada);
  });

  test("se a decodificacao falhar, devolve o arquivo original", async () => {
    global.createImageBitmap = () => Promise.reject(new Error("formato desconhecido"));
    const entrada = arquivo("estranho.heic");
    await expect(comprimirImagem(entrada)).resolves.toBe(entrada);
  });

  test("nunca lanca — envio travado e pior que envio grande", async () => {
    global.createImageBitmap = () => {
      throw new Error("explodiu");
    };
    await expect(comprimirImagem(arquivo())).resolves.toBeDefined();
  });
});
