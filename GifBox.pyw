# -*- coding: utf-8 -*-
"""GifBox 창 실행기. (.pyw 라서 검은 콘솔 창이 뜨지 않습니다)"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gifbox.gui import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
