"""Authenticated Elite search: permission, matching, persistence and stale edits. No network/database."""
import asyncio
import copy
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
sys.path.insert(0,str(Path(__file__).parent.parent))
import nutrition_routes as routes
from billing_plans import BUSCA_ALIMENTOS_PLANO, capacidades_do_plano

@pytest.fixture
def setup(monkeypatch):
    foods={key:{'id':key,'name':name,'grams':100,'kcal':1,'protein_g':1,'carbs_g':1,'fat_g':1} for key,name in [('old','Original'),('a','Arroz branco'),('b','Feijão cozido')]}
    monkeypatch.setattr(routes,'FOOD_INDEX',foods)
    monkeypatch.setattr(routes,'build_food_item',lambda fid,grams:{'food_id':fid,'grams':grams,'food':foods[fid]})
    monkeypatch.setattr(routes,'find_substitutes',lambda *args,**kwargs:[('a',100,'allowed'),('b',100,'allowed')])
    plan={'source':'manual_import','targets':{'unchanged':True},'meals':[{'name':'Almoço','foods':[{'food_id':'old','grams':100}]}]}
    db=SimpleNamespace(
        subscriptions=SimpleNamespace(find_one=AsyncMock(return_value={'plan_code':'elite','status':'active'})),
        profiles=SimpleNamespace(find_one=AsyncMock(return_value={'nutrition_assessment':{}})),
        nutrition_plans=SimpleNamespace(find_one=AsyncMock(side_effect=lambda *args:copy.deepcopy({'plan':plan})),update_one=AsyncMock(return_value=SimpleNamespace(matched_count=1))))
    request=SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(db=db)))
    user={'id':'owner','role':'ATHLETE','signup_source':'public'}
    return db,request,user,plan

def call(setup,**kwargs):
    _,request,user,_=setup
    return asyncio.run(routes.substitute_food(routes.SubstituteFoodIn(meal_index=0,food_id='old',food_index=0,**kwargs),request,user))

@pytest.mark.parametrize('code',['essential','pro'])
@pytest.mark.parametrize('applying',[False,True])
def test_non_elite_cannot_search_or_save(setup,code,applying):
    setup[0].subscriptions.find_one.return_value={'plan_code':code,'status':'active'}
    with pytest.raises(HTTPException) as error:call(setup,search='',substitute_food_id='a' if applying else None)
    assert error.value.status_code==402
    setup[0].nutrition_plans.update_one.assert_not_called()
    assert BUSCA_ALIMENTOS_PLANO not in capacidades_do_plano(code)

def test_elite_search_ignores_case_accents_and_word_order(setup):
    result=call(setup,search='COZIDO feijao')
    assert [o['food_id'] for o in result['options']]==['b']
    setup[0].nutrition_plans.update_one.assert_not_called()
    assert BUSCA_ALIMENTOS_PLANO in capacidades_do_plano('elite')

def test_empty_search_result_does_not_fabricate_food(setup):
    assert call(setup,search='not in catalog')['options']==[]

def test_elite_save_persists_own_plan_with_compare_and_swap(setup):
    db,_,_,before=setup
    result=call(setup,search='',substitute_food_id='b')
    selection,update=db.nutrition_plans.update_one.call_args.args
    assert selection=={'profile_id':'owner','plan.meals':before['meals']}
    assert update['$set']['plan.meals.0.foods'][0]['food_id']=='b'
    assert result['plan']['targets']==before['targets']
    assert result['plan']['meals'][0]['foods'][0]['food_id']=='b'

def test_changed_plan_returns_conflict(setup):
    setup[0].nutrition_plans.update_one.return_value=SimpleNamespace(matched_count=0)
    with pytest.raises(HTTPException) as error:call(setup,search='',substitute_food_id='a')
    assert error.value.status_code==409

def test_unapproved_food_cannot_be_saved_even_by_elite(setup):
    with pytest.raises(HTTPException) as error:call(setup,search='',substitute_food_id='forged')
    assert error.value.status_code==400
    setup[0].nutrition_plans.update_one.assert_not_called()

def test_legacy_suggestions_remain_available_to_pro(setup):
    setup[0].subscriptions.find_one.return_value={'plan_code':'pro','status':'active'}
    assert len(call(setup)['options'])==2
