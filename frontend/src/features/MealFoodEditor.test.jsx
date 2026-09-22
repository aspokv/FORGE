import React,{act} from 'react';
import {createRoot} from 'react-dom/client';
import axios from 'axios';
import MealFoodEditor from './MealFoodEditor';
jest.mock('axios',()=>({post:jest.fn()}));
global.IS_REACT_ACT_ENVIRONMENT=true;
let host,root,onSaved,onClose;
const meal={name:'Almoço',foods:[{food_id:'original',food:{name:'Alimento original'}},{food_id:'original',food:{name:'Segunda porção'}}]};
const options=[{food_id:'beans',food:{name:'Feijão cozido'}}];
beforeEach(()=>{jest.useFakeTimers();axios.post.mockReset();onSaved=jest.fn();onClose=jest.fn();host=document.createElement('div');document.body.appendChild(host);root=createRoot(host);});
afterEach(async()=>{await act(async()=>root.unmount());host.remove();jest.useRealTimers();});
const render=()=>act(async()=>root.render(<MealFoodEditor API="/api" meal={meal} mealIndex={2} onSaved={onSaved} onClose={onClose}/>));
const change=(selector,value)=>act(async()=>{const node=document.querySelector(selector);const proto=node.tagName==='SELECT'?HTMLSelectElement.prototype:HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(proto,'value').set.call(node,value);node.dispatchEvent(new Event('change',{bubbles:true}));node.dispatchEvent(new Event('input',{bubbles:true}));});
const tick=()=>act(async()=>jest.advanceTimersByTime(250));
const button=text=>[...document.querySelectorAll('button')].find(b=>b.textContent===text);
const click=element=>act(async()=>element.click());
async function choose(){axios.post.mockResolvedValueOnce({data:{options}});await change('input[type="search"]','feijao');await tick();await click(document.querySelector('input[type="radio"]'));}

test('searches by typed name and saves the selected occurrence permanently',async()=>{
 await render();await change('select','1');await choose();
 expect(axios.post.mock.calls[0][1]).toEqual({meal_index:2,food_id:'original',food_index:1,search:'feijao'});
 const plan={meals:[{name:'Almoço',foods:options}]};
 axios.post.mockResolvedValueOnce({data:{applied:true,plan}});
 await click(button('Salvar troca no plano'));
 expect(axios.post.mock.calls[1][1]).toEqual({meal_index:2,food_id:'original',food_index:1,substitute_food_id:'beans',search:''});
 expect(onSaved).toHaveBeenCalledWith(plan);expect(onClose).toHaveBeenCalledTimes(1);
});
test('failed save preserves the choice and permits retry',async()=>{
 await render();await choose();axios.post.mockRejectedValueOnce(new Error('offline'));
 await click(button('Salvar troca no plano'));
 expect(document.querySelector('[role="alert"]').textContent).toContain('Sua escolha continua aqui');
 expect(document.querySelector('input[type="radio"]').checked).toBe(true);
 expect(button('Salvar troca no plano').disabled).toBe(false);expect(onClose).not.toHaveBeenCalled();
 axios.post.mockResolvedValueOnce({data:{applied:true,plan:{meals:[]}}});await click(button('Salvar troca no plano'));
 expect(onSaved).toHaveBeenCalledTimes(1);
});
test('ignores a stale response after the user changes the search',async()=>{
 await render();let resolveOld;axios.post.mockImplementationOnce(()=>new Promise(resolve=>{resolveOld=resolve;}));
 await change('input[type="search"]','arroz');await tick();
 axios.post.mockResolvedValueOnce({data:{options}});await change('input[type="search"]','feijao');await tick();
 await act(async()=>resolveOld({data:{options:[{food_id:'rice',food:{name:'Resultado antigo'}}]}}));
 expect(document.body.textContent).toContain('Feijão cozido');expect(document.body.textContent).not.toContain('Resultado antigo');
});
test('cancelling before a search never changes the plan',async()=>{
 await render();await click(button('Cancelar'));expect(onClose).toHaveBeenCalledTimes(1);
 expect(axios.post).not.toHaveBeenCalled();expect(onSaved).not.toHaveBeenCalled();
});
test('handles access revocation with a specific message',async()=>{
 await render();axios.post.mockRejectedValueOnce({response:{status:402}});
 await change('input[type="search"]','feijao');await tick();
 expect(document.querySelector('[role="alert"]').textContent).toContain('exclusiva do Elite');
 expect(button('Salvar troca no plano').disabled).toBe(true);
});
