"""Isolated capability checks; no server startup or database access."""
import ast
import asyncio
from pathlib import Path
import unittest
from unittest.mock import AsyncMock
from billing_plans import CAPACIDADES_PRO, CAPACIDADES_ELITE, CAPACIDADES_ESSENCIAL, VARIACOES_DE_TREINO


class VariationAccessTests(unittest.TestCase):
    def test_pro_and_elite_include_variations(self):
        self.assertIn(VARIACOES_DE_TREINO, CAPACIDADES_PRO)
        self.assertIn(VARIACOES_DE_TREINO, CAPACIDADES_ELITE)
        self.assertNotIn(VARIACOES_DE_TREINO, CAPACIDADES_ESSENCIAL)

    def test_apply_checks_access_before_any_profile_read_or_write(self):
        tree=ast.parse(Path(__file__).with_name('server.py').read_text(encoding='utf-8-sig'))
        fn=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='apply_workout_template')
        fn.decorator_list=[]
        for arg in fn.args.args:
            arg.annotation=None
        fn.args.defaults=[]
        fn.returns=None
        gate=AsyncMock(side_effect=PermissionError('requires Pro'))
        namespace={'exigir_capacidade':gate,'db':object(),'VARIACOES_DE_TREINO':VARIACOES_DE_TREINO}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'apply_guard_test','exec'),namespace)
        with self.assertRaises(PermissionError):
            asyncio.run(namespace['apply_workout_template'](object(),{'id':'test'}))
        gate.assert_awaited_once()


if __name__=='__main__':
    unittest.main()
