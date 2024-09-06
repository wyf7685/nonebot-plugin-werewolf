# ruff: noqa: T201

import os
import tomllib
from datetime import date
from pathlib import Path

os.system("pdm lint")

project_root = Path(__file__).parent.parent.resolve()

toml_file = project_root / "pyproject.toml"
project = tomllib.loads(toml_file.read_text(encoding="utf-8"))

project_name: str = project["project"]["name"]
print(f"Project name: {project_name}")

old_ver: str = project["project"]["version"]
print(f"Current version: {old_ver}")
new_ver = input("Input new version: ")

changelog: list[str] = []
while line := input("Input changelog: "):
    changelog.append(line)

today = date.today().strftime("%Y.%m.%d")


def replace_file(path: Path, old: str, new: str):
    path.write_text(
        path.read_text(encoding="utf-8").replace(old, new),
        encoding="utf-8",
        newline="\n",
    )


init_file = project_root / project_name.replace("-", "_") / "__init__.py"
replace_file(
    init_file,
    f'__version__ = "{old_ver}"',
    f'__version__ = "{new_ver}"',
)
replace_file(
    toml_file,
    f'version = "{old_ver}"',
    f'version = "{new_ver}"',
)

changelog_placeholder = "<!-- CHANGELOG -->"
new_changelog = (
    changelog_placeholder
    + f"\n\n- {today} v{new_ver}\n\n"
    + "\n".join(f"  - {line}" for line in changelog)
)
readme_file = project_root / "README.md"
replace_file(
    readme_file,
    changelog_placeholder,
    new_changelog,
)

os.system("git add -u")
os.system(f'git commit -m "version {new_ver}"')
os.system(f"git tag v{new_ver}")

print("Done!")
