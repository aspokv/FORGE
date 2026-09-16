import {build} from 'esbuild';
import {readFileSync,writeFileSync,readdirSync} from 'node:fs';
const model=readFileSync('public/models/forge-device.glb').toString('base64');
const result=await build({entryPoints:['src/main.jsx'],bundle:true,write:false,minify:true,format:'iife',target:'es2022',jsx:'automatic',define:{'process.env.NODE_ENV':'"production"','import.meta.env.BASE_URL':'"./"'},plugins:[{name:'standalone',setup(b){
 b.onLoad({filter:/\.css$/},()=>({contents:'',loader:'css'}));
 b.onLoad({filter:/src\/config\.js$/},args=>({contents:readFileSync(args.path,'utf8').replace('`${import.meta.env.BASE_URL}models/forge-device.glb`',JSON.stringify('data:model/gltf-binary;base64,'+model)),loader:'js'}));
 b.onLoad({filter:/screenSequence\.js$/},args=>({contents:readFileSync(args.path,'utf8').replace(/`\$\{import\.meta\.env\.BASE_URL\}screens\/([^`]+)`/g,(_,file)=>JSON.stringify('data:image/'+(file.endsWith('.jpg')?'jpeg':'png')+';base64,'+readFileSync('public/screens/'+file).toString('base64'))),loader:'js'}));
}}],outfile:'preview.js'});
const js=result.outputFiles.find(f=>f.path.endsWith('.js')).text.replace(/<\/script/gi,'<\\/script');
const cssPath=readdirSync('dist/assets').find(f=>f.endsWith('.css'));const css=readFileSync('dist/assets/'+cssPath,'utf8');
const favicon='data:image/svg+xml;base64,'+readFileSync('public/favicon.svg').toString('base64');
const html=`<!doctype html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#090909"><title>FORGE — Protótipo com telas reais</title><link rel="icon" href="${favicon}"><style>${css}</style></head><body><div id="root"></div><script>${js}</script></body></html>`;
writeFileSync('../forge-prototipo.html',html);console.log(`Standalone HTML: ${Buffer.byteLength(html)} bytes; 7 original captures embedded`);
