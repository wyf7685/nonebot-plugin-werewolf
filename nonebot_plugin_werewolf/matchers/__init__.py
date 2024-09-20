def load() -> None:
    import importlib
    import pathlib

    for path in pathlib.Path(__file__).parent.iterdir():
        if not path.name.startswith("_") and path.suffix == ".py":
            importlib.import_module(f"{__name__}.{path.stem}")
