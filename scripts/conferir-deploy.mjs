/**
 * Confere se um deploy chegou de fato ao ar, procurando marcadores no que e SERVIDO.
 *
 * Duas armadilhas ja produziram resposta errada aqui, e as duas estao tratadas:
 *
 * FALSO POSITIVO — usar como prova uma string que ja existia antes do commit. Ela casa na
 * primeira tentativa e da verde imediato. Antes de confiar num marcador, prove que ele e
 * inedito:
 *     git log --oneline -S "<marcador>" -- frontend/src
 * tem de devolver exatamente UM commit, o seu. Sucesso na primeira tentativa e suspeito:
 * o build leva cerca de dois minutos.
 *
 * FALSO NEGATIVO — procurar so em `static/css/main.*.css`. Parte do CSS e do JS sai em
 * chunks separados, que o index.html nem cita. Por isso este roteiro monta a lista de
 * arquivos a partir do MAPA DE CHUNKS do webpack, dentro do main.js.
 *
 * MARCADOR RUIM — ineditismo no git nao basta; o marcador tem de SOBREVIVER ao build.
 * Nome de funcao, de variavel ou de modulo (`parDeAvaliacoes`) e apagado pelo minificador
 * e da "AUSENTE" num deploy que chegou. Acento tambem atrapalha: o texto vem escapado no
 * bundle e a comparacao falha. Marcador confiavel e ASCII e preservado — classe de CSS,
 * `data-testid`, ou um trecho sem acento de um texto de tela ("carregar esta foto").
 *
 * A prova completa e um par: o marcador novo presente E o texto antigo ausente.
 *
 * Uso:
 *   node scripts/conferir-deploy.mjs https://forge.aiexec.com.br "marcador novo" ...
 *   node scripts/conferir-deploy.mjs <url> --esperar "marcador"   (aguarda o build)
 */
const args = process.argv.slice(2);
const base = (args.shift() || "").replace(/\/$/, "");
const esperar = args[0] === "--esperar";
if (esperar) args.shift();
const marcadores = args;

if (!base || !marcadores.length) {
  console.error('uso: node scripts/conferir-deploy.mjs <url> [--esperar] "marcador" ...');
  process.exit(2);
}

const pegar = async (url) => {
  const r = await fetch(url, { cache: "no-store" });
  return r.ok ? r.text() : "";
};

/** Todos os arquivos servidos: os citados no index mais os do mapa de chunks do webpack. */
async function arquivosServidos() {
  const index = await pegar(`${base}/index.html?t=${Date.now()}`);
  const citados = [...index.matchAll(/(?:src|href)="(\/static\/[^"]+\.(?:js|css))"/g)]
    .map((m) => m[1]);

  const nomes = new Set(citados);
  for (const caminho of citados.filter((c) => c.endsWith(".js"))) {
    const js = await pegar(base + caminho);
    // O mapa e do tipo  "static/js/"+e+"."+{ 183:"4cf0f9d4", ... }+".chunk.js"
    for (const bloco of js.matchAll(/"static\/(js|css)\/"\+\w+\+"\."\+(\{[^}]+\})/g)) {
      const [, tipo, mapa] = bloco;
      for (const par of mapa.matchAll(/(\d+):"([a-f0-9]+)"/g)) {
        const sufixo = tipo === "js" ? ".chunk.js" : ".chunk.css";
        nomes.add(`/static/${tipo}/${par[1]}.${par[2]}${sufixo}`);
      }
    }
  }
  return [...nomes];
}

async function conferir() {
  const caminhos = await arquivosServidos();
  const conteudos = await Promise.all(
    caminhos.map(async (c) => [c, await pegar(base + c)])
  );
  const bytes = conteudos.reduce((s, [, t]) => s + t.length, 0);

  const achados = marcadores.map((m) => {
    const onde = conteudos.filter(([, t]) => t.includes(m)).map(([c]) => c.slice(1));
    return [m, onde];
  });
  return { caminhos, bytes, achados };
}

const espera = (ms) => new Promise((r) => setTimeout(r, ms));
const TENTATIVAS = esperar ? 30 : 1;

for (let i = 1; i <= TENTATIVAS; i += 1) {
  const { caminhos, bytes, achados } = await conferir();
  const faltando = achados.filter(([, onde]) => !onde.length);

  if (!faltando.length || i === TENTATIVAS) {
    console.log(`${caminhos.length} arquivos servidos por ${base} (${bytes} bytes)\n`);
    for (const [m, onde] of achados) {
      console.log(`  ${m.padEnd(28)} ${onde.length ? "em " + onde.join(", ") : "AUSENTE"}`);
    }
    if (esperar && !faltando.length) console.log(`\nPUBLICADO na tentativa ${i}`);
    process.exit(faltando.length ? 1 : 0);
  }
  console.log(`[${i}] ainda nao publicado; aguardando`);
  await espera(30000);
}
