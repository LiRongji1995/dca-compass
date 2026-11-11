"""dca-dashboard 命令：等价于 streamlit run app.py。"""

import sys
from pathlib import Path


def main() -> None:
    from streamlit.web import cli

    app = Path(__file__).with_name("app.py")
    sys.argv = ["streamlit", "run", str(app), *sys.argv[1:]]
    sys.exit(cli.main())
