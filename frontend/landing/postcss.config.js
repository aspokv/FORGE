/*
 * Vazio de proposito, e ele precisa existir.
 *
 * O PostCSS procura configuracao subindo de diretorio. Sem este arquivo, o Vite da landing
 * encontrava `frontend/postcss.config.js`, que e do aplicativo CRA e carrega Tailwind 3 —
 * e o Tailwind 3 nao entende `@import 'tailwindcss'`, que e sintaxe da versao 4. O build
 * quebrava com um erro que parecia da landing e vinha do vizinho.
 *
 * O Tailwind 4 aqui entra pelo plugin do Vite (@tailwindcss/vite), entao nao ha nada para
 * o PostCSS fazer.
 */
export default { plugins: {} };
