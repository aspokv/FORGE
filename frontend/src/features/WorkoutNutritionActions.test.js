import React,{act} from 'react';
import {createRoot} from 'react-dom/client';
import axios from 'axios';
import WorkoutVariationsButton,{sessionCategory} from './WorkoutVariationsButton';
import NutritionDailyFooter from './NutritionDailyFooter';
jest.mock('axios',()=>({get:jest.fn(),post:jest.fn(),delete:jest.fn()}));
global.IS_REACT_ACT_ENVIRONMENT=true;

test.each([['Pull 2','pull'],['Push 1','push'],['Upper A','upper'],['Lower B','lower'],['Full Body','full_body'],['Pernas','legs']])('opens matching category for %s',(label,expected)=>{
  expect(sessionCategory({label})).toBe(expected);
});

test.each([true,false])('variation shortcut respects capability: %s',async allowed=>{
  axios.get.mockResolvedValue({data:{capabilities:allowed?['workout_variations']:[]}});
  const host=document.createElement('div'),root=createRoot(host),open=jest.fn();
  await act(async()=>root.render(<WorkoutVariationsButton onOpen={open}/>));
  const button=host.querySelector('button');
  expect(button.disabled).toBe(!allowed);
  await act(async()=>button.click());
  expect(open).toHaveBeenCalledTimes(allowed?1:0);
  await act(async()=>root.unmount());
});

test('hydration controls use saved totals and daily summary includes actual macros',async()=>{
  axios.get.mockResolvedValue({data:{total_ml:500,goal_ml:2000}});
  axios.post.mockResolvedValue({data:{total_ml:750,goal_ml:2000}});
  const host=document.createElement('div'),root=createRoot(host);
  await act(async()=>root.render(<NutritionDailyFooter API="/api" consumed={{kcal:1200,protein_g:100,carbs_g:120,fat_g:35}} goalCalories={2000}/>));
  expect(host.textContent).toContain('800 kcal restantes');
  expect(host.textContent).not.toContain('Whey');
  await act(async()=>host.querySelector('.daily-water-actions button').click());
  expect(axios.post).toHaveBeenCalledWith(expect.stringMatching(/\/api\/hydration\/\d{4}-\d{2}-\d{2}$/),{amount_ml:250});
  expect(host.querySelector('progress').value).toBe(750);
  await act(async()=>root.unmount());
});
