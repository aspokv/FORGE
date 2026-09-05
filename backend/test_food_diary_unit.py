"""Isolated HTTP tests; never imports server or connects to MongoDB."""
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from auth import get_current_user
from nutrition_routes import router
from food_diary import DIARY_FOODS


class Collection:
    def __init__(self):
        self.rows = {}

    async def update_one(self, query, update, upsert=False):
        self.rows[query['_id']] = {**self.rows.get(query['_id'], {}), **update['$set']}

    async def find_one(self, query):
        return next((copy.deepcopy(r) for r in self.rows.values() if all(r.get(k) == v for k, v in query.items())), None)

    def find(self, query, projection=None):
        rows = [copy.deepcopy(r) for r in self.rows.values() if all(r.get(k) == v for k, v in query.items())]
        class Cursor:
            def sort(self, key, direction):
                rows.sort(key=lambda r: r.get(key, ''))
                return self
            async def to_list(self, limit):
                return rows
        return Cursor()

    async def delete_one(self, query):
        row = self.rows.get(query['_id'])
        if row and row['profile_id'] == query['profile_id']:
            del self.rows[query['_id']]


class FoodDiaryTests(unittest.TestCase):
    def test_ground_beef_is_in_consumed_food_catalog(self):
        self.assertIn('beef-ground', DIARY_FOODS)
        self.assertIn('carne moída', DIARY_FOODS['beef-ground']['name'].lower())

    def setUp(self):
        self.db = SimpleNamespace(nutrition_adherence=Collection(), nutrition_consumed_extras=Collection(), nutrition_plans=Collection())
        self.db.nutrition_plans.rows['plan'] = {'profile_id': 'alice', 'plan': {'meals': [{'name': 'Almoço'}]}}
        app = FastAPI()
        app.state.db = self.db
        app.include_router(router)
        self.user = {'id': 'alice'}
        app.dependency_overrides[get_current_user] = lambda: self.user
        self.client = TestClient(app)
        self.entitlement = patch('nutrition_routes.exigir_capacidade', new_callable=AsyncMock)
        self.entitlement_mock = self.entitlement.start()
        self.addCleanup(self.entitlement.stop)
        self.payload = {'date': '2026-09-03', 'meal_index': 0, 'entry_id': '00000000-0000-4000-8000-000000000001', 'foods': [{'food_id': 'diary-beef-ribs-roasted', 'grams': 150}]}

    def test_catalog_load_does_not_depend_on_billing_lookup(self):
        self.entitlement_mock.side_effect = RuntimeError('billing unavailable')
        response = self.client.get('/api/nutrition/consumed-foods')
        self.assertEqual(response.status_code, 200, response.text)
        ground = next(f for f in response.json()['foods'] if f['id'] == 'beef-ground')
        self.assertIn('carne moida', ground['aliases'])

    def test_catalog_has_popular_whey_brands_without_external_dependency(self):
        response = self.client.get('/api/nutrition/consumed-foods')
        names = " ".join(food['name'] for food in response.json()['foods'])
        for brand in ('Growth Supplements', 'Max Titanium', 'Integralmédica', 'DUX Nutrition', 'Optimum Nutrition'):
            self.assertIn(brand, names)

    def test_replacement_persists_server_calculation_without_changing_plan(self):
        before = copy.deepcopy(self.db.nutrition_plans.rows)
        r = self.client.post('/api/nutrition/consumed-meal', json=self.payload)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()['actual']['totals']['kcal'], 540)
        self.assertEqual(self.db.nutrition_plans.rows, before)
        meals = self.client.get('/api/nutrition/adherence/2026-09-03').json()['meals']
        self.assertEqual(meals[0]['actual']['totals']['protein_g'], 42.75)

    def test_retry_does_not_duplicate_extra(self):
        self.payload['meal_index'] = None
        for _ in range(2):
            self.assertEqual(self.client.post('/api/nutrition/consumed-meal', json=self.payload).status_code, 200)
        self.assertEqual(len(self.db.nutrition_consumed_extras.rows), 1)

    def test_owner_and_date_isolation(self):
        self.payload['meal_index'] = None
        self.client.post('/api/nutrition/consumed-meal', json=self.payload)
        self.assertEqual(self.client.get('/api/nutrition/adherence/2026-09-04').json()['extras'], [])
        self.user = {'id': 'bob'}
        self.client.delete('/api/nutrition/consumed-extra/' + self.payload['entry_id'])
        self.assertEqual(len(self.db.nutrition_consumed_extras.rows), 1)
        self.assertEqual(self.client.get('/api/nutrition/adherence/2026-09-03').json()['extras'], [])

    def test_skip_clears_actual_and_repeated_status_has_one_row(self):
        self.client.post('/api/nutrition/consumed-meal', json=self.payload)
        for _ in range(2):
            self.client.post('/api/nutrition/meal-status', json={'meal_index': 0, 'date': self.payload['date'], 'status': 'skipped'})
        meals = self.client.get('/api/nutrition/adherence/2026-09-03').json()['meals']
        self.assertEqual(len(meals), 1)
        self.assertEqual(meals[0]['status'], 'skipped')
        self.assertIsNone(meals[0]['actual'])

    def test_invalid_portions_and_unknown_food_rejected(self):
        for grams in [0, -1, 5001, 'NaN']:
            self.payload['foods'][0]['grams'] = grams
            self.assertEqual(self.client.post('/api/nutrition/consumed-meal', json=self.payload).status_code, 422)
        self.payload['foods'] = [{'food_id': 'unknown', 'grams': 100}]
        self.assertEqual(self.client.post('/api/nutrition/consumed-meal', json=self.payload).status_code, 422)
        self.assertEqual(self.db.nutrition_adherence.rows, {})

    def test_invalid_meal_and_date_rejected(self):
        self.payload['meal_index'] = 4
        self.assertEqual(self.client.post('/api/nutrition/consumed-meal', json=self.payload).status_code, 422)
        self.payload['date'] = 'invalid'
        self.assertEqual(self.client.post('/api/nutrition/consumed-meal', json=self.payload).status_code, 422)

    def test_owner_can_remove_extra(self):
        self.payload['meal_index'] = None
        self.client.post('/api/nutrition/consumed-meal', json=self.payload)
        self.client.delete('/api/nutrition/consumed-extra/' + self.payload['entry_id'])
        self.assertEqual(self.db.nutrition_consumed_extras.rows, {})


if __name__ == '__main__':
    unittest.main()
