import {consumedTotals} from './foodDiary';

const meals=[{target_cal:600,foods:[{grams:150,food:{grams:100,kcal:200,protein_g:20,carbs_g:10,fat_g:8}}]}];
test('planned consumption uses portion weights',()=>{
  expect(consumedTotals(meals,[{meal_index:0,status:'completed'}]).kcal).toBe(300);
});
test('actual meal replaces planned calories, extras are added once',()=>{
  const before=JSON.stringify(meals);
  const totals=consumedTotals(meals,[{meal_index:0,status:'completed',actual:{totals:{kcal:480,protein_g:30}}}],[{actual:{totals:{kcal:100}}}]);
  expect(totals.kcal).toBe(580);
  expect(totals.protein_g).toBe(30);
  expect(JSON.stringify(meals)).toBe(before);
});
test('latest status wins and skipped meal is not counted',()=>{
  expect(consumedTotals(meals,[{meal_index:0,status:'completed'},{meal_index:0,status:'skipped'}]).kcal).toBe(0);
});
test('zero calorie actual entry never falls back to original meal',()=>{
  expect(consumedTotals(meals,[{meal_index:0,status:'completed',actual:{totals:{kcal:0}}}]).kcal).toBe(0);
});
test('extras also work without a meal plan',()=>{
  expect(consumedTotals(undefined,[],[{actual:{totals:{kcal:360}}}]).kcal).toBe(360);
});
