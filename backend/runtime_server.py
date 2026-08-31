"""Guaranteed FORGE backend runtime bootstrap.

Install structural training-engine extensions before server.py imports any engine symbols.
"""
import engine
from training_engine_v4 import install as install_v4
from training_engine_v5 import install as install_v5

install_v4(engine)
install_v5(engine)

from server import app  # noqa: E402,F401
