/*
 * Service worker do FORGE — deliberadamente sem cache.
 *
 * Ele existe por um motivo so: o Chrome no Android exige um service worker com tratador de
 * `fetch` para oferecer "Instalar aplicativo". Sem ele a pessoa consegue no maximo "adicionar
 * a tela inicial" pelo menu.
 *
 * NAO guarda nada, e isso e escolha, nao esquecimento. O FORGE publica varias vezes por dia;
 * um cache mal ajustado prenderia o atleta numa versao antiga do aplicativo sem ele entender
 * por que a tela nao muda — e depurar isso no telefone de outra pessoa e quase impossivel.
 * Entre funcionar sem internet e nunca servir versao velha, a segunda ganha aqui.
 *
 * Se um dia valer a pena ter modo offline, o caminho e cachear SO os arquivos com hash no
 * nome (`/static/...`), que sao imutaveis por construcao, e jamais o `index.html`.
 */

// Assume o controle das abas abertas assim que instala, sem esperar elas fecharem.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (evento) => evento.waitUntil(self.clients.claim()));

// Repasse puro. O tratador precisa existir; guardar resposta, nao.
self.addEventListener("fetch", (evento) => {
  if (evento.request.method !== "GET") return;
  evento.respondWith(fetch(evento.request));
});
