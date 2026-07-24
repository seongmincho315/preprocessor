import os
import sys

sys.path.insert(0, os.path.abspath("../facade"))

project = "doc-parser-preprocessor"
copyright = "GenOS"
author = "GenOS"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
]

autosummary_generate = True
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
}
autodoc_typehints = "description"
napoleon_google_docstring = True
napoleon_numpy_docstring = False

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "furo"
html_static_path = ["_static"]
html_title = "doc-parser-preprocessor"
html_logo = "_static/logo.png"
html_favicon = "_static/logo.png"

# docs/extra/ 밑의 파일/디렉터리를 Sphinx 처리 없이 빌드 결과물 루트로 그대로 복사한다.
# config_generator/index.html이 여기 있어서 배포되면
# https://<user>.github.io/<repo>/config_generator/ 로 그대로 서빙된다.
html_extra_path = ["extra"]
