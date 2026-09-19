"""Guaranteed FORGE backend runtime bootstrap.

Install structural training-engine extensions and user-authored Custom programs before
server.py imports the application.
"""
import engine
import training_programs
from training_engine_v4 import install as install_v4
from training_engine_v5 import install as install_v5
from training_engine_hybrid import install as install_hybrid
from custom_training_programs import install as install_custom_programs

install_v4(engine)
install_v5(engine)
# O Hybrid entra por ULTIMO, e a ordem importa: ele embrulha o construtor que o v5 deixou,
# e delega para ele toda divisao que nao for hibrida. Instalado antes do v5, o v5
# sobrescreveria `build_all_sessions` e o hibrido nunca seria chamado.
install_hybrid(engine)
install_custom_programs(training_programs)

# `server.py` monta o cardio router junto com todos os outros. Ele ficava aqui, e so aqui,
# o que deixava `server:app` — a aplicacao que a suite inteira importa — sem rota de
# cardio. Montar nos dois lugares registraria a mesma rota duas vezes.
from server import app  # noqa: E402,F401
