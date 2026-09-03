import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import axios from 'axios';
import FoodDiaryEditor from './FoodDiaryEditor';
jest.mock('axios',()=>({get:jest.fn(),post:jest.fn()}));

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
