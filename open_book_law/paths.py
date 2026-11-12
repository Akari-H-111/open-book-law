"""Where the data lives. Downloaded data stays outside the repository.

Set OBL_DATA to the data folder. Without it, the code looks in `data_local/` inside the repository,
which git ignores and which may be a symbolic link to the real folder.
"""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = Path(os.environ.get("OBL_DATA", REPO_ROOT / "data_local"))
DERIVED_DIR = DATA_ROOT / "derived"
