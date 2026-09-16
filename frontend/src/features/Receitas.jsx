import {useCallback, useEffect, useState} from "react";
import axios from "axios";
import {ChefHat, Clock} from "lucide-react";
import "./receitas.css";
import {mensagemDeErro} from "./mensagemDeErro";

/**
 * As receitas do FORGE.
 *
 * O que separa esta tela de um livro de receitas nao e o conteudo, e o ENCAIXE: cada
 * receita e montada com os alimentos do proprio catalogo, entao o servidor calcula a
 * caloria de verdade e responde a unica pergunta que interessa a quem segue um plano —
 * "isto cabe no meu lanche da tarde?".
 *
 * O alvo nao e calculado aqui. Ele vem do plano da pessoa, resolvido no servidor: a tela
 * nao precisa saber traduzir "sobremesa" para "lanche da tarde", e assim nao existe como
 * as duas discordarem.
 *
 * Fechada por padrao, como o resto dos blocos da Nutricao: quem abre a Nutricao vem ver o
 * plano do dia, e nao procurar receita. Aberta, ela empurraria o plano para fora da tela.
 */
export default function Receitas({API}) {
  const [aberto, setAberto] = useState(false);
  const [classes, setClasses] = useState(null);
  const [classe, setClasse] = useState(null);
  const [livres, setLivres] = useState(false);
  const [lista, setLista] = useState(null);
  const [expandida, setExpandida] = useState(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    if (!aberto || classes) return;
    let vivo = true;
    axios.get(`${API}/nutrition/receitas/classes`)
      .then(r => { if (vivo) setClasses(r.data?.classes || []); })
      .catch(e => { if (vivo) setErro(mensagemDeErro(e, "Não foi possível carregar as receitas.")); });
    return () => { vivo = false; };
  }, [API, aberto, classes]);

  const buscar = useCallback(() => {
    let vivo = true;
    setLista(null); setExpandida(null); setErro("");
    const params = {};
    if (livres) params.livres = true;
    else if (classe) params.classe = classe;
    axios.get(`${API}/nutrition/receitas`, {params})
      .then(r => { if (vivo) setLista(r.data?.receitas || []); })
      .catch(e => { if (vivo) setErro(mensagemDeErro(e, "Não foi possível carregar as receitas.")); });
    return () => { vivo = false; };
  }, [API, classe, livres]);

  useEffect(() => { if (aberto) return buscar(); }, [aberto, buscar]);

  const escolherClasse = (chave) => { setLivres(false); setClasse(chave); };

  return (
    <section className="receitas" data-testid="receitas">
      <button type="button" className="receitas-topo" aria-expanded={aberto}
              data-testid="abrir-receitas" onClick={() => setAberto(v => !v)}>
        <ChefHat size={17} aria-hidden="true" />
        <span>
          <strong>Receitas</strong>
          <small>Feitas com os alimentos do seu plano — o FORGE diz se cabem na sua refeição.</small>
        </span>
        <span className="receitas-seta" aria-hidden="true">{aberto ? "▾" : "▸"}</span>
      </button>

      {aberto && <div className="receitas-corpo">
        {!classes && !erro && <div className="fg-esqueleto" aria-label="Carregando receitas" />}

        {classes && <div className="receitas-abas" role="tablist" aria-label="Classes de receita">
          <button type="button" role="tab" aria-selected={!classe && !livres}
                  className={`receitas-aba${!classe && !livres ? " marcada" : ""}`}
                  data-testid="aba-todas"
                  onClick={() => { setLivres(false); setClasse(null); }}>Todas</button>
          {classes.map(c => (
            <button type="button" key={c.chave} role="tab" aria-selected={classe === c.chave && !livres}
                    className={`receitas-aba${classe === c.chave && !livres ? " marcada" : ""}`}
                    data-testid={`aba-${c.chave}`} onClick={() => escolherClasse(c.chave)}>
              {c.rotulo} <em>{c.quantas}</em>
            </button>
          ))}
          {/*
            * A refeicao livre e aba propria, e nao um filtro escondido: e o pedido do
            * treinador e e o que a pessoa procura quando bate a vontade de doce. Ela cruza
            * as classes de proposito — o que define uma receita livre nao e a hora do dia.
            */}
          <button type="button" role="tab" aria-selected={livres}
                  className={`receitas-aba receitas-aba-livre${livres ? " marcada" : ""}`}
                  data-testid="aba-refeicao-livre"
                  onClick={() => { setClasse(null); setLivres(true); }}>Refeição livre</button>
        </div>}

        {livres && <p className="receitas-nota">
          Doce de verdade, feito só com o que já está no seu plano. Por isso ele cabe na
          conta do dia em vez de estourá-la.
        </p>}

        {erro && <p className="fg-erro" role="alert">{erro}</p>}
        {!lista && !erro && classes && <div className="fg-esqueleto" aria-label="Carregando" />}

        {lista && lista.map(r => {
          const aberta = expandida === r.id;
          return (
            <article className="receita" key={r.id} data-testid={`receita-${r.id}`}>
              <button type="button" className="receita-topo" aria-expanded={aberta}
                      data-testid={`abrir-${r.id}`}
                      onClick={() => setExpandida(x => x === r.id ? null : r.id)}>
                <span className="receita-nome">
                  <b>{r.nome}</b>
                  {r.refeicao_livre && <em className="receita-selo">refeição livre</em>}
                </span>
                <small>{r.resumo}</small>
                <span className="receita-numeros">
                  <b>{r.kcal}<i>kcal</i></b>
                  <span>P {r.protein_g} · C {r.carbs_g} · G {r.fat_g}</span>
                  <span className="receita-tempo"><Clock size={12} aria-hidden="true" /> {r.tempo_min} min</span>
                  {r.rendimento > 1 && <span>rende {r.rendimento}</span>}
                </span>
                {/*
                  * O encaixe so aparece quando o servidor conseguiu achar a refeicao
                  * correspondente no plano. Sem plano montado nao ha alvo, e inventar um
                  * numero aqui seria pior do que nao dizer nada.
                  */}
                {r.encaixe && (
                  <span className={`receita-encaixe${r.encaixe.cabe ? "" : " nao"}`}
                        data-testid={`encaixe-${r.id}`}>
                    {r.encaixe.cabe
                      ? `Cabe no seu ${r.classe_rotulo.toLowerCase()} de ${r.encaixe.alvo} kcal` +
                        (r.encaixe.sobra > 0 ? ` — sobram ${r.encaixe.sobra} kcal` : "")
                      : `Passa ${r.encaixe.excedeu} kcal do seu ${r.classe_rotulo.toLowerCase()}`}
                  </span>
                )}
              </button>

              {aberta && <div className="receita-corpo">
                <p className="receita-porque">{r.por_que}</p>

                <p className="fg-etiqueta">Ingredientes</p>
                <ul className="receita-ingredientes">
                  {r.ingredientes.map(i => (
                    <li key={i.food_id}><span>{i.nome}</span><b>{i.gramas} g</b></li>
                  ))}
                  {(r.extras || []).map(e => (
                    <li className="receita-extra" key={e}><span>{e}</span></li>
                  ))}
                </ul>
                {r.rendimento > 1 && <p className="receita-aviso">
                  As quantidades são da receita inteira, que rende {r.rendimento} porções.
                  Os valores acima já são de <b>uma</b> porção.
                </p>}

                <p className="fg-etiqueta">Modo de preparo</p>
                <ol className="receita-preparo">
                  {r.preparo.map((passo, i) => <li key={i}>{passo}</li>)}
                </ol>
              </div>}
            </article>
          );
        })}

        {lista && lista.length === 0 && (
          <p className="receitas-nota">Nenhuma receita nesta aba ainda.</p>
        )}
      </div>}
    </section>
  );
}
