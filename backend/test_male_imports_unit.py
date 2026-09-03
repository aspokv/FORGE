import json
import unittest
from pathlib import Path
from training_programs import public_program_catalog


class MaleImportsTests(unittest.TestCase):
    def setUp(self):
        self.programs = {p['id']:p for p in public_program_catalog()['programs'] if p['id'].startswith('male-')}

    def test_all_nine_programs_are_male_and_author_free(self):
        self.assertEqual(len(self.programs),9)
        self.assertEqual({p['category'] for p in self.programs.values()},{'abc','abcd','abcde','abcdef'})
        for p in self.programs.values():
            self.assertEqual(p['audience_type'],'male')
            self.assertEqual(p['duration_weeks'],0)
            self.assertEqual(p['safety'],'expert')
            self.assertIn('RIR',p['phases'][0]['note'])
        text=json.dumps(self.programs,ensure_ascii=False).lower()
        for name in ['pacholok','fabrício','charles','brandão','nescau']:
            self.assertNotIn(name,text)

    def test_catalog_and_builder_shapes(self):
        catalog=json.loads(Path(__file__).with_name('exercises.json').read_text(encoding='utf-8'))
        ids={e['id'] for e in catalog}
        self.assertEqual(len(ids),len(catalog))
        for p in self.programs.values():
            for s in p['phases'][0]['sessions']:
                entries=[e['exercise_id'] for e in s['exercises']]
                self.assertEqual(len(entries),len(set(entries)),s['label'])
                self.assertTrue(set(entries)<=ids,set(entries)-ids)
                for e in s['exercises']:
                    self.assertTrue(1<=e['sets']<=12)
                    self.assertTrue(e['rest'] and e['reps'])

    def test_two_periods_are_not_silently_merged(self):
        for id,count in [('male-abcde-professional',7),('male-book-abcde-3',7),('male-book-abcd-pro',6)]:
            p=self.programs[id]
            self.assertEqual(len(p['phases'][0]['sessions']),count)
            self.assertIn('não agenda automaticamente',p['phases'][0]['note'])
            self.assertIn('5–6 horas',p['warning'])

    def test_source_order_and_uncertainty(self):
        p=self.programs['male-abcde-five-day']['phases'][0]
        legs=p['sessions'][1]['exercises']
        self.assertEqual([e['exercise_id'] for e in legs],['bb-squat','hack-squat','leg-press','leg-extension','lying-leg-curl','rdl'])
        self.assertEqual(p['sessions'][2]['exercises'][0]['sets'],1)
        self.assertIn('divergindo',p['sessions'][0]['exercises'][0]['note'])
        self.assertEqual(self.programs['male-abcde-professional']['phases'][0]['sessions'][1]['exercises'][4]['sets'],6)

    def test_book_blueprints_are_explicit_adaptations(self):
        for id,p in self.programs.items():
            if 'book-' in id:
                self.assertEqual(p['phases'][0]['method'],'Modelo adaptado')
                self.assertIn('espaços por grupo muscular',p['description'])


if __name__=='__main__': unittest.main()
