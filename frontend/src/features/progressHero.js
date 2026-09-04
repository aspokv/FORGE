export function buildProgressHero({trend=[],prs=[],bodyTrend=[]}={}){
  const points=(trend||[]).filter(x=>Number(x.load)>0);
  const trendChange=points.length>1&&Number(points[0].load)>0
    ?((Number(points.at(-1).load)-Number(points[0].load))/Number(points[0].load)*100)
    :null;
  const results=(prs||[]).filter(p=>Number(p.weight??String(p.value||"").replace(",",".").match(/[\d.]+/)?.[0])>0);
  const weights=(bodyTrend||[]).filter(x=>Number(x.weight)>0);

  if(weights.length){
    const current=Number(weights.at(-1).weight);
    const delta=weights.length>1?current-Number(weights[0].weight):null;
    return {
      value:`${current.toLocaleString("pt-BR",{maximumFractionDigits:1})} kg`,
      copy:delta==null
        ?"Peso atual registrado. Continue atualizando para acompanhar a tendência corporal."
        :`${delta>=0?"+":""}${delta.toFixed(1).replace(".",",")} kg no período registrado · acompanhe junto com sua evolução de treino.`
    };
  }

  if(trendChange!=null){
    return {
      value:`${trendChange>=0?"+":""}${trendChange.toFixed(1).replace(".",",")}% de carga`,
      copy:"Comparação das últimas quatro semanas com registros válidos."
    };
  }

  return {
    value:results.length?"Evolução em construção":"Primeira linha de base criada",
    copy:results.length
      ?"Seus melhores resultados já estão abaixo. Registre seu peso para acompanhar também a evolução corporal."
      :"Complete seus treinos e registre seu peso para transformar os primeiros dados em tendência."
  };
}
