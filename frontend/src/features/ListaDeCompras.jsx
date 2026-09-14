import {useEffect,useMemo,useState} from "react";
import axios from "axios";
import {ShoppingCart} from "lucide-react";
import {semanaDoCalendario} from "./semanaDaDieta";
import "./lista-de-compras.css";

/**
 * A lista de compras da semana, dentro da Nutricao.
 *
 * Fechada por padrao. Ela so interessa no dia da compra, e aberta sempre empurraria o plano
 * do dia — que e o que a pessoa olha todo dia — para fora da primeira dobra.
 *
 * A semana vem do APARELHO, pelo mesmo motivo da aba Dieta: o servidor roda em UTC e o
 * atleta vive em UTC-3, entao a segunda-feira calculada la erraria o dia no fim da noite. E
 * como a semana e a chave do que ja foi marcado, a lista zera sozinha na virada.
 */
export default function ListaDeCompras({API}){
  const semana=useMemo(()=>semanaDoCalendario(new Date()),[]);
  const [lista,setLista]=useState(null),[erro,setErro]=useState("");
  const [aberta,setAberta]=useState(false),[salvando,setSalvando]=useState(null);

  useEffect(()=>{
    if(!aberta||lista)return;
    let vivo=true;
    axios.get(`${API}/nutrition/shopping-list`,{params:{week_start:semana.inicio,days:7}})
      .then(r=>{if(vivo)setLista(r.data)})
      .catch(()=>{if(vivo)setErro("Não foi possível montar a lista. Tente abrir de novo.")});
    return()=>{vivo=false};
  },[API,aberta,lista,semana.inicio]);

  /*
   * A marca aparece na hora e so depois vai ao servidor. No corredor do mercado, com sinal
   * ruim, esperar a resposta para o quadradinho mudar faria a pessoa tocar duas vezes. Se a
   * gravacao falhar, desfaz e avisa — nunca fica marcado sem ter sido salvo.
   */
  const marcar=async(item,comprado)=>{
    setSalvando(item.food_id);setErro("");
    const antes=lista;
    setLista(l=>({...l,
      comprados:l.comprados+(comprado?1:-1),
      secoes:l.secoes.map(s=>({...s,itens:s.itens.map(i=>i.food_id===item.food_id?{...i,comprado}:i)}))}));
    try{
      await axios.post(`${API}/nutrition/shopping-list/check`,
        {food_id:item.food_id,comprado,week_start:semana.inicio});
    }catch{
      setLista(antes);
      setErro("Não foi possível salvar essa marcação.");
    }finally{setSalvando(null)}
  };

  const total=lista?.total_de_itens||0,comprados=lista?.comprados||0;
  const curta=iso=>String(iso||"").slice(5).split("-").reverse().join("/");

  return <section className="lista-compras" data-testid="lista-de-compras">
    <button type="button" className="lista-compras-topo" aria-expanded={aberta} onClick={()=>setAberta(v=>!v)}>
      <ShoppingCart size={17} aria-hidden="true"/>
      <span>
        <strong>Lista de compras</strong>
        <small>Semana de {curta(semana.inicio)} a {curta(semana.fim)}</small>
      </span>
      {lista&&<b>{comprados} de {total}</b>}
    </button>

    {aberta&&<div className="lista-compras-corpo">
      {erro&&<p className="lista-compras-erro" role="alert">{erro}</p>}
      {!lista&&!erro&&<p role="status">Montando sua lista…</p>}

      {lista&&<>
        <div className="lista-compras-barra" role="progressbar" aria-label="Itens comprados"
             aria-valuemin="0" aria-valuemax={total} aria-valuenow={comprados}>
          <span style={{width:total?`${comprados/total*100}%`:"0%"}}/>
        </div>

        {lista.secoes.map(secao=><div className="lista-compras-secao" key={secao.chave}>
          <h4>{secao.titulo}</h4>
          <ul>
            {secao.itens.map(item=><li key={item.food_id} className={item.comprado?"comprado":undefined}>
              <label>
                <input type="checkbox" checked={!!item.comprado} disabled={salvando===item.food_id}
                       onChange={e=>marcar(item,e.target.checked)}/>
                <span className="lista-compras-nome">{item.nome}</span>
                {/*
                  * "crus" vai COLADO no numero, e nao no rodape. Quem conhece a propria
                  * dieta tem 1,75 kg de arroz na cabeca; ver 583 g solto parece erro do
                  * aplicativo, e rodape ninguem le.
                  */}
                <span className="lista-compras-qtd">
                  {item.compra.texto}{item.convertido&&<i>{" "}{item.estado}</i>}
                  {item.compra.unidade&&<small>~{item.compra.unidade}</small>}
                </span>
              </label>
            </li>)}
          </ul>
        </div>)}

        {/*
          * O aviso nao e rodape decorativo: o peso mostrado e de COMPRA, convertido do peso
          * do prato. Sem dizer isso, quem confere a embalagem contra o plano acha que um dos
          * dois esta errado.
          */}
        <p className="lista-compras-nota">
          Pesos para comprar, já convertidos do peso pronto do seu plano — arroz e feijão
          rendem mais depois de cozidos, carne encolhe. São valores aproximados.
        </p>
      </>}
    </div>}
  </section>;
}
