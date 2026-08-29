import fs from "fs";
import path from "path";

/**
 * A CSP e a pagina precisam concordar.
 *
 * Se alguem voltar a colocar um `<script>` inline no index.html, a pagina quebra em
 * producao — silenciosamente, porque o navegador so recusa o script e segue. Este teste
 * transforma isso num erro de build em vez de um bug de campo.
 */

const RAIZ = path.join(__dirname, "..", "..");
const BRUTO = fs.readFileSync(path.join(RAIZ, "nginx.conf"), "utf8");
const INDEX = fs.readFileSync(path.join(RAIZ, "public", "index.html"), "utf8");

// Sem as linhas de comentario: elas falam SOBRE as diretivas, e o parser as confundia
// com as proprias diretivas.
const NGINX = BRUTO.split("\n")
  .filter((l) => !l.trim().startsWith("#"))
  .join("\n");

/** Valor de uma diretiva de dentro da CSP. */
function diretiva(nome) {
  const csp = NGINX.match(/add_header Content-Security-Policy "([^"]+)"/);
  if (!csp) return null;
  const parte = csp[1].split(";").map((x) => x.trim())
    .find((x) => x.startsWith(nome + " "));
  return parte ? parte.slice(nome.length + 1).trim() : null;
}

/** O cabecalho existe com "always"? O valor pode conter ponto-e-virgula (HSTS contem). */
function temCabecalho(nome) {
  return new RegExp(`add_header ${nome} "[^"]*"\\s+always;`).test(NGINX);
}

describe("script-src", () => {
  test("nao permite script inline", () => {
    expect(diretiva("script-src")).toBe("'self'");
    expect(diretiva("script-src")).not.toContain("unsafe-inline");
    expect(diretiva("script-src")).not.toContain("unsafe-eval");
  });

  test("o index.html nao tem script inline", () => {
    const inline = INDEX.match(/<script(?![^>]*\ssrc=)[^>]*>[\s\S]*?<\/script>/g) || [];
    expect(inline).toEqual([]);
  });

  test("o tratador de DataCloneError vive num arquivo proprio", () => {
    expect(INDEX).toMatch(/<script src="[^"]*silenciar-dataclone\.js"/);
    const arquivo = path.join(RAIZ, "public", "silenciar-dataclone.js");
    expect(fs.existsSync(arquivo)).toBe(true);
    expect(fs.readFileSync(arquivo, "utf8")).toMatch(/DataCloneError/);
  });

  test("todo script do index carrega da propria origem", () => {
    const externos = [...INDEX.matchAll(/<script[^>]*\ssrc="([^"]+)"/g)].map((m) => m[1]);
    expect(externos.length).toBeGreaterThan(0);
    externos.forEach((src) => expect(src).not.toMatch(/^https?:\/\//));
  });
});

describe("as demais diretivas", () => {
  test("nada pode enquadrar a pagina", () => {
    expect(diretiva("frame-ancestors")).toBe("'none'");
    expect(NGINX).toMatch(/X-Frame-Options "DENY"/);
  });

  test("objeto e base ficam fechados", () => {
    expect(diretiva("object-src")).toBe("'none'");
    expect(diretiva("base-uri")).toBe("'self'");
  });

  test("as requisicoes so saem para a propria origem", () => {
    expect(diretiva("connect-src")).toBe("'self'");
  });

  test("as fontes externas sao apenas as do Google Fonts", () => {
    expect(diretiva("font-src")).toBe("'self' https://fonts.gstatic.com data:");
    expect(diretiva("style-src")).toContain("https://fonts.googleapis.com");
  });

  test("style-src ainda permite inline, e isso esta documentado", () => {
    // Risco residual assumido: o React aplica style= em dezenas de pontos. O comentario
    // ao lado da diretiva precisa continuar explicando o porque — sem ele, a proxima
    // pessoa nao sabe se e descuido ou decisao.
    expect(diretiva("style-src")).toContain("'unsafe-inline'");
    // O comentario vive no arquivo bruto, nao no filtrado.
    expect(BRUTO).toMatch(/style-src AINDA tem 'unsafe-inline'/);
  });
});

describe("cabecalhos de seguranca", () => {
  test.each([
    "Strict-Transport-Security",
    "X-Content-Type-Options",
    "Referrer-Policy",
    "Permissions-Policy",
    "Content-Security-Policy",
    "X-Frame-Options",
  ])("%s e enviado com always", (cabecalho) => {
    expect(temCabecalho(cabecalho)).toBe(true);
  });

  test("a versao do nginx nao e anunciada", () => {
    expect(NGINX).toMatch(/server_tokens off;/);
  });
});
