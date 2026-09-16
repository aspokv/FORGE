export const PRODUCT = {
  // Replace this file with any GLB. Named parts enable the exploded choreography.
  modelUrl: `${import.meta.env.BASE_URL}models/forge-device.glb`,
  dracoPath: `${import.meta.env.BASE_URL}draco/`,
  parts: {body:'Body', rim:'Rim', screen:'Screen', nutrition:'Nutrition', evolution:'Evolution'},
  finishes: [{name:'Obsidiana',color:'#252525',metalness:.92,roughness:.22},{name:'Titânio',color:'#a9a5a0',metalness:.95,roughness:.29}],
};
export const CHAPTERS = [
 {tag:'UM SISTEMA. A SUA ROTINA.',title:['Seu próximo','nível tem um','sistema.'],body:'Treino, alimentação e evolução. Conectados para acompanhar você.',label:'Conheça o Forge',detail:'Tudo começa na sua tela de Início'},
 {tag:'01 / NUTRIÇÃO',title:['Sua alimentação.','No seu ritmo.'],body:'Uma visão das suas refeições, dos seus registros e das escolhas que fazem parte da rotina.',label:'Explore a nutrição',detail:'Sua alimentação, organizada'},
 {tag:'02 / SUAS ESCOLHAS',title:['Escolha o que','combina com você.'],body:'Explore combinações ou monte sua refeição. Seus alimentos e preferências fazem parte do plano.',label:'Conheça o sistema',detail:'Combinações ou montagem do zero'},
 {tag:'03 / PERSONALIZAÇÃO',title:['Sua rotina muda.','O plano acompanha.'],body:'Reúna suas preferências e ajuste o plano dentro do mesmo sistema.',label:'Explore os recursos',detail:'Personalização em um só lugar'},
 {tag:'04 / RECEITAS',title:['Variedade.','Todos os dias.'],body:'Encontre receitas por tipo de refeição, com ingredientes, modo de preparo e tempo.',label:'Conheça os recursos',detail:'29 receitas para variar a rotina'},
 {tag:'05 / BIBLIOTECA',title:['Encontre seu','próximo programa.'],body:'Explore programas completos e sessões avulsas. Veja a estrutura antes de aplicar à sua rotina.',label:'Explore a biblioteca',detail:'23 programas · 24 sessões avulsas'},
 {tag:'06 / TREINO',title:['Uma sessão termina.','Sua rotina continua.'],body:'Veja a sessão concluída, consulte seu programa e acompanhe o próximo treino no mesmo lugar.',label:'Encontre seu plano',detail:'Seu histórico. Seu próximo passo.'},
];
// `code` e o mesmo codigo que o backend usa em billing_plans.py. Ele viaja na URL ate o
// cadastro, que envia SO o codigo ao checkout: preco e periodicidade vem da allow-list do
// servidor, nunca do navegador.
export const PLANS=[
 {name:'Essencial',code:'essential',price:'39,90',tag:'A base da sua rotina.',features:['Treino personalizado','Substituição de exercícios','Histórico de sessões','Acesso no celular e computador']},
 {name:'Pro',code:'pro',price:'69,90',tag:'Treino e alimentação, juntos.',features:['Tudo do Essencial','Plano alimentar personalizado','Substituições alimentares','Acompanhamento integrado']},
 {name:'Elite',code:'elite',price:'99,90',tag:'Mais liberdade para montar.',features:['Tudo do Pro','Modo de treino manual','Importação de treino por texto','Maior personalização']},
];

// Para onde os botoes levam. O aplicativo FORGE vive no mesmo dominio, entao sao caminhos
// absolutos e navegacao de pagina inteira: a landing e um site estatico e o aplicativo e
// outro pacote.
export const ASSINAR = code => `/assinar?plano=${code}`;
export const ENTRAR = '/login';
