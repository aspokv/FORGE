"""Guaranteed FORGE backend runtime bootstrap.

Install structural training-engine extensions and user-authored Custom programs before
server.py imports the application.
"""
import engine
import training_programs
from training_engine_v4 import install as install_v4
from training_engine_v5 import install as install_v5
from custom_training_programs import install as install_custom_programs

install_v4(engine)
install_v5(engine)
install_custom_programs(training_programs)

from server import app  # noqa: E402,F401
from cardio_routes import router as cardio_router  # noqa: E402

app.include_router(cardio_router)
