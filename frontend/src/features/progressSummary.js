export function buildProgressSummary({trendChange=null,resultCount=0}={}){
  const numericChange=Number(trendChange);
  if(trendChange!==null&&trendChange!==undefined&&Number.isFinite(numericChange)){
    return {
      eyebrow:"VISÃO GERAL",
      value:`${numericChange>=0?"+":""}${numericChange.toFixed(1).replace(".",",")}% na carga média`,
      copy:"Comparação das últimas quatro semanas com registros válidos."
    };
  }
  if(Number(resultCount)>0){
    const count=Number(resultCount);
    return {
      eyebrow:"VISÃO GERAL",
      value:`${count} ${count===1?"exercício acompanhado":"exercícios acompanhados"}`,
      copy:"Seus melhores resultados estão organizados logo abaixo."
    };
  }
  return {
    eyebrow:"VISÃO GERAL",
    value:"Seu progresso começa aqui",
    copy:"Registre seus treinos para acompanhar seus resultados ao longo do tempo."
  };
}
