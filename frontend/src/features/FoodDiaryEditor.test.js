import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import axios from 'axios';
import FoodDiaryEditor,{matchesFoodQuery} from './FoodDiaryEditor';
jest.mock('axios',()=>({get:jest.fn(),post:jest.fn()}));

test('search ignores accents and includes aliases',()=>{
  const food={name:'Carne moída (acém)',aliases:['carne moida refogada','guizado']};
  expect(matchesFoodQuery(food,'carne moida')).toBe(true);
  expect(matchesFoodQuery(food,'guizado')).toBe(true);
  expect(matchesFoodQuery(food,'carne frango')).toBe(false);
});

test('save retry preserves id and sends weighed foods instead of client calories',async()=>{
  global.IS_REACT_ACT_ENVIRONMENT=true;
  Object.defineProperty(global,'crypto',{configurable:true,value:{randomUUID:()=> '00000000-0000-4000-8000-000000000001'}});
  axios.get.mockResolvedValue({data:{foods:[{id:'ribs',name:'Costela',grams:100,kcal:360}]}});
  axios.post.mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({data:{}});
  const div=document.createElement('div'),root=createRoot(div),close=jest.fn(),saved=jest.fn();
  await act(async()=>root.render(<FoodDiaryEditor API="/api" mealIndex={0} mealName="Almoço" onSaved={saved} onClose={close}/>));
  await act(async()=>div.querySelector('.food-diary-results button').click());
  const save=div.querySelector('.primary-button');
  await act(async()=>save.click());
  expect(div.querySelector('[role="alert"]')).not.toBeNull();
  expect(close).not.toHaveBeenCalled();
  await act(async()=>save.click());
  expect(axios.post.mock.calls[0][1]).toEqual(axios.post.mock.calls[1][1]);
  expect(axios.post.mock.calls[1][1].foods).toEqual([{food_id:'ribs',grams:100}]);
  expect(saved).toHaveBeenCalledTimes(1);
  expect(close).toHaveBeenCalledTimes(1);
  await act(async()=>root.unmount());
});

test.each([360,375,390,412])('search stays above the keyboard at %i px and restores the shell',async(width)=>{
  global.IS_REACT_ACT_ENVIRONMENT=true;
  const originalViewport=Object.getOwnPropertyDescriptor(window,'visualViewport');
  const originalWidth=window.innerWidth,originalHeight=window.innerHeight;
  const viewport=Object.assign(new EventTarget(),{height:800,offsetTop:0,scale:1});
  Object.defineProperty(window,'visualViewport',{configurable:true,value:viewport});
  window.innerWidth=width;
  window.innerHeight=800;
  const raf=jest.spyOn(window,'requestAnimationFrame').mockImplementation(fn=>{fn();return 1;});
  axios.get.mockResolvedValue({data:{foods:[{id:'sweet-potato',name:'Batata doce',grams:100,kcal:86}]}});
  const div=document.createElement('div');
  document.body.appendChild(div);
  const root=createRoot(div);
  try {
    await act(async()=>root.render(<div className="forge-shell"><div className="a6"><div className="a6-scroll"><FoodDiaryEditor API="/api" onSaved={()=>{}} onClose={()=>{}}/></div></div></div>));
    const shell=div.querySelector('.forge-shell'),page=div.querySelector('.a6'),scroll=div.querySelector('.a6-scroll'),input=div.querySelector('input');
    expect(document.activeElement).not.toBe(input);
    input.getBoundingClientRect=()=>({top:600});
    scroll.getBoundingClientRect=()=>({top:63});
    await act(async()=>input.focus());
    expect(shell.hasAttribute('data-food-keyboard')).toBe(false);
    viewport.height=350;
    await act(async()=>viewport.dispatchEvent(new Event('resize')));
    expect(shell.getAttribute('data-food-keyboard')).toBe('open');
    expect(page.style.getPropertyValue('--food-diary-viewport')).toBe('350px');
    expect(scroll.scrollTop).toBeGreaterThan(0);
    expect(div.querySelector('.food-diary-results').textContent).toContain('Batata doce');
    // A layout-resizing Android browser must also retain the keyboard adjustment.
    window.innerHeight=350;
    await act(async()=>window.dispatchEvent(new Event('resize')));
    expect(shell.getAttribute('data-food-keyboard')).toBe('open');
    await act(async()=>input.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true})));
    expect(document.activeElement).not.toBe(input);
    expect(shell.hasAttribute('data-food-keyboard')).toBe(false);
    expect(page.style.getPropertyValue('--food-diary-viewport')).toBe('');
    viewport.height=800;
    window.innerHeight=800;
    await act(async()=>viewport.dispatchEvent(new Event('resize')));
    await act(async()=>input.focus());
    viewport.height=350;
    viewport.scale=2;
    await act(async()=>viewport.dispatchEvent(new Event('resize')));
    expect(shell.hasAttribute('data-food-keyboard')).toBe(false);
    viewport.scale=1;
    await act(async()=>viewport.dispatchEvent(new Event('resize')));
    expect(shell.hasAttribute('data-food-keyboard')).toBe(true);
    await act(async()=>root.unmount());
    expect(shell.hasAttribute('data-food-keyboard')).toBe(false);
  } finally {
    await act(async()=>root.unmount());
    div.remove();
    raf.mockRestore();
    window.innerWidth=originalWidth;
    window.innerHeight=originalHeight;
    if(originalViewport)Object.defineProperty(window,'visualViewport',originalViewport);
    else delete window.visualViewport;
  }
});
