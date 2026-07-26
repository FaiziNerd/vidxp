from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - legacy fallback
    import tomli as tomllib  # type: ignore

from setuptools import find_packages, setup


ROOT = Path(__file__).resolve().parent


def load_project_metadata() -> dict:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]


def read_long_description() -> str:
    return (ROOT / "README.md").read_text(encoding="utf-8")


project = load_project_metadata()
primary_author = project["authors"][0] if project.get("authors") else {}
primary_author_name = primary_author.get("name")
primary_author_email = primary_author.get("email")

setup(
    name=project["name"],
    version=project["version"],
    description=project["description"],
    long_description=read_long_description(),
    long_description_content_type="text/markdown",
    author=primary_author_name,
    author_email=primary_author_email,
    python_requires=project["requires-python"],
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    entry_points={"console_scripts": ["vidxp=vidxp.main:main"]},
)
