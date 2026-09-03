export const localFoodDate = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
};
export function consumedTotals(meals=[], logs=[], extras=[]) {
  const total={kcal:0,protein_g:0,carbs_g:0,fat_g:0};
  const add=m=>Object.keys(total).forEach(k=>{total[k]+=Number(m?.[k]||0)});
  const latest=new Map(logs.map(row=>[Number(row.meal_index),row]));
  latest.forEach((row,i)=>{
    if(row.status!=="completed")return;
    if(row.actual){add(row.actual.totals);return;}
    const meal=meals[i];
    if(!meal)return;
    if(!meal.foods?.length){add({kcal:meal.target_cal});return;}
    meal.foods.forEach(item=>{
      const f=item.food||{},ratio=Number(item.grams||0)/Number(f.grams||100);
      add(Object.fromEntries(Object.keys(total).map(k=>[k,Number(f[k]||0)*ratio])));
    });
  });
  extras.forEach(row=>add(row.actual?.totals));
  return total;
}
