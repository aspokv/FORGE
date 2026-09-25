/**
 * A tabela de trocas que veio escrita na dieta colada.
 *
 * Uma dieta de nutricionista traz, depois das refeições, as equivalências que ela mesma
 * autoriza — "250 g batata inglesa → 200 g batata-doce → 150 g aipim". O importador lia
 * essas linhas como comida a mais na ceia. Agora elas viram esta tabela, com os números
 * que a dieta escreveu: não são recalculados, porque são a palavra de quem prescreveu.
 */
function gramas(valor) {
  const n = Number(valor);
  if (!Number.isFinite(n) || n <= 0) return "";
  return `${Number.isInteger(n) ? n : n.toFixed(1).replace(".", ",")} g`;
}

export function agruparTrocas(trocas) {
  const grupos = [];
  for (const troca of trocas || []) {
    const opcoes = (troca?.opcoes || []).filter(o => o && (o.name || o.food_id));
    if (opcoes.length < 2) continue;
    const titulo = troca.titulo || "Substituições";
    let grupo = grupos.find(g => g.titulo === titulo);
    if (!grupo) grupos.push(grupo = {titulo, linhas: []});
    grupo.linhas.push(opcoes);
  }
  return grupos;
}

export default function TrocasDaDieta({trocas}) {
  const grupos = agruparTrocas(trocas);
  if (!grupos.length) return null;
  return (
    <section className="fg-trocas" data-testid="trocas-da-dieta">
      <div className="a6-section-title"><h2>Trocas da sua dieta</h2></div>
      {grupos.map(grupo => (
        <div className="fg-trocas-grupo" key={grupo.titulo}>
          <p className="fg-etiqueta">{grupo.titulo}</p>
          <ul>
            {grupo.linhas.map((opcoes, i) => (
              <li key={i}>
                {opcoes.map((opcao, j) => (
                  <span className="fg-troca-opcao" key={j}>
                    {/* Espaço de verdade, e não margem: leitor de tela e copiar-colar
                        leriam "cozidaou200". */}
                    {j > 0 && <span className="fg-troca-ou">{" ou "}</span>}
                    {gramas(opcao.grams) && <b>{gramas(opcao.grams)}</b>} {opcao.name || opcao.food_id}
                  </span>
                ))}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}
