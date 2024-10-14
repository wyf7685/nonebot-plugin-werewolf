@ECHO OFF
isort .
black .
pyright .
ruff check .
