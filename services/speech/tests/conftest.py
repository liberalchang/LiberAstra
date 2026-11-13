from __future__ import annotations

import sys
from pathlib import Path

SPEECH_ROOT = Path(__file__).resolve().parents[1]
if str(SPEECH_ROOT) not in sys.path:
    sys.path.insert(0, str(SPEECH_ROOT))
