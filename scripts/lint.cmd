@ECHO OFF
uv run isort .
uv run black .
uv run pyright .
uv run ruff check .
