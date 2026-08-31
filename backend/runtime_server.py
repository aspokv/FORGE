"""Guaranteed FORGE backend runtime bootstrap.

Install structural training-engine extensions before server.py imports any engine symbols.
"""
import engine
from training_engine_v4 import install

install(engine)

from server import app  # noqa: E402,F401
