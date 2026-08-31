"""Runtime bootstrap for FORGE backend extensions.

Python imports ``sitecustomize`` automatically during interpreter startup when this
module is available on sys.path. The backend container uses /app as WORKDIR, so this
activates the structural training engine before FastAPI imports ``engine`` symbols.
"""
try:
    import engine
    from training_engine_v4 import install

    install(engine)
except Exception:
    # Never make the API unbootable because an optional runtime extension failed.
    # The existing v3 engine remains available and healthchecks expose any regression.
    pass
