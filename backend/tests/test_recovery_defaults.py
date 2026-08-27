"""Motor de progressao: recovery AUSENTE significa NORMAL, nunca deload.

Bug 1 do fluxo de conclusao: o frontend gravava um recovery inventado
(sleep 4, energy 3, soreness 2, stress 2) a cada "Concluir treino". O motor le os 3
ultimos registros, entao depois de tres treinos o atleta ficava permanentemente em
VERY_LOW — 2 series a menos em cada exercicio e RIR "3+" no programa inteiro — sem
nunca ter respondido nada sobre o proprio descanso.

Testes puros: nao precisam de banco nem de servidor.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import _apply_recovery_adjustment, _get_recent_recovery


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_sem_registro_de_recovery_o_nivel_e_normal():
    assert _run(_get_recent_recovery(None, "qualquer-atleta"))["level"] == "NORMAL"


def test_normal_nao_mexe_na_prescricao():
    assert _apply_recovery_adjustment(4, "1-2", "HIGH", "NORMAL", "compound") == (4, "1-2")


def test_os_valores_fabricados_pontuavam_abaixo_do_limiar_de_very_low():
    energy, stress, soreness = 3, 2, 2          # o que o app mandava sozinho
    assert energy * 2 - stress - soreness == 2  # limiar de VERY_LOW e < 3


def test_very_low_corta_duas_series_e_forca_rir_3mais():
    assert _apply_recovery_adjustment(4, "1-2", "HIGH", "VERY_LOW", "compound") == (2, "3+")


def test_recovery_real_continua_influenciando_o_motor():
    """Remover o recovery fabricado nao pode desligar a adaptacao de verdade."""
    assert _apply_recovery_adjustment(4, "1-2", "HIGH", "LOW", "compound") == (3, "3")
