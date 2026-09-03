import json
import unittest
from pathlib import Path
from training_programs import public_program_catalog


class FemaleImportsTests(unittest.TestCase):
    def test_three_programs_are_female_and_have_source_names(self):
        programs={p['id']:p for p in public_program_catalog()['programs'] if p['id'].startswith('female-')}
        self.assertEqual(set(programs),{'female-november-abcd','female-advanced-7','female-shape-de-cavala'})
        for id,days,split in [('female-november-abcd',4,'abcd'),('female-advanced-7',6,'abcdef'),('female-shape-de-cavala',5,'abcde')]:
            self.assertEqual(programs[id]['audience_type'],'female')
            self.assertEqual(programs[id]['days_per_week'],days)
            self.assertEqual(programs[id]['category'],split)
        self.assertEqual(programs['female-shape-de-cavala']['name'],'Treino Shape de Cavala')
        self.assertEqual(programs['female-advanced-7']['duration_weeks'],8)
        content=json.dumps(programs,ensure_ascii=False).lower()
        for author in ['rubens','gomes','balestrin','júlio']:
            self.assertNotIn(author,content)

    def test_all_exercises_exist_and_no_duplicate_ids_within_session(self):
        catalog=json.loads(Path(__file__).with_name('exercises.json').read_text(encoding='utf-8'))
        ids={e['id'] for e in catalog}
        self.assertEqual(len(ids),len(catalog))
        for p in public_program_catalog()['programs']:
            if not p['id'].startswith('female-'): continue
            for s in p['phases'][0]['sessions']:
                entries=[e['exercise_id'] for e in s['exercises']]
                self.assertEqual(len(entries),len(set(entries)))
                self.assertTrue(set(entries)<=ids)

    def test_missing_information_remains_explicit(self):
        p=next(p for p in public_program_catalog()['programs'] if p['id']=='female-shape-de-cavala')
        self.assertEqual(p['duration_weeks'],0)
        self.assertEqual(p['safety'],'expert')
        self.assertIn('não define',p['phases'][0]['note'])
        kickback=next(e for e in p['phases'][0]['sessions'][2]['exercises'] if e['exercise_id']=='cable-glute-kickback')
        self.assertIn('ausentes',kickback['note'])


if __name__=='__main__': unittest.main()
