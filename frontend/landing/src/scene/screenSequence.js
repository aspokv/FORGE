// Owner-supplied screenshots, copied byte-for-byte. No generated app screens.
export const SCREEN_CAPTURES = {
 home:{label:'Início',src:`${import.meta.env.BASE_URL}screens/inicio.jpg`,width:1210,height:2048},
 nutrition:{label:'Nutrição',src:`${import.meta.env.BASE_URL}screens/nutricao-real.jpg`,width:1200,height:2048},
 meals:{label:'Monte sua refeição',src:`${import.meta.env.BASE_URL}screens/montar-refeicao.jpg`,width:1193,height:2048},
 preferences:{label:'Preferências',src:`${import.meta.env.BASE_URL}screens/preferencias.jpg`,width:1204,height:2048},
 recipes:{label:'Receitas',src:`${import.meta.env.BASE_URL}screens/receitas.jpg`,width:1208,height:2048},
 library:{label:'Biblioteca',src:`${import.meta.env.BASE_URL}screens/biblioteca.jpg`,width:1206,height:2048},
 training:{label:'Treino',src:`${import.meta.env.BASE_URL}screens/sessao.jpg`,width:1201,height:2048},
};
export const SCREEN_SEQUENCE = ['home','nutrition','meals','preferences','recipes','library','training'];
export const CAPTURE_ASPECT = 1200/2048;
export function screenBlend(progress){
 const p=Math.max(0,Math.min(1,progress));
 for(let i=1;i<SCREEN_SEQUENCE.length;i++){
  const boundary=i/SCREEN_SEQUENCE.length;
  const start=boundary-.022,end=boundary+.022;
  if(p<start)return {from:SCREEN_SEQUENCE[i-1],to:SCREEN_SEQUENCE[i-1],mix:0,turn:0};
  if(p<=end){const t=(p-start)/(end-start);return {from:SCREEN_SEQUENCE[i-1],to:SCREEN_SEQUENCE[i],mix:t*t*(3-2*t),turn:Math.sin(t*Math.PI)*.22};}
 }
 const last=SCREEN_SEQUENCE.at(-1);return {from:last,to:last,mix:0,turn:0};
}
