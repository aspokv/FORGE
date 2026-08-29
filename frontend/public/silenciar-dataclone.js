/* Silencia um erro que nao e da aplicacao.
 *
 * Algumas extensoes de navegador tentam clonar PerformanceServerTiming, que nao e
 * clonavel, e o DataCloneError resultante aparece no console como se fosse do FORGE.
 * O tratador ignora exatamente esse caso e nada mais.
 *
 * Vive num arquivo proprio, e nao inline no index.html, para a CSP poder usar
 * script-src 'self' sem 'unsafe-inline': um script inline exigiria hash, e o hash muda
 * a cada build porque o minificador reescreve o codigo.
 */
window.addEventListener("error", function (e) {
  if (
    e.error instanceof DOMException &&
    e.error.name === "DataCloneError" &&
    e.message &&
    e.message.includes("PerformanceServerTiming")
  ) {
    e.stopImmediatePropagation();
    e.preventDefault();
  }
}, true);
