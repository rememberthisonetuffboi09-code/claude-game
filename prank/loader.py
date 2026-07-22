"""The 'fake DLL' theater: a convincing-looking mod loader that's pure show.

None of this touches memory or a real process. It just prints a believable
injection sequence so the prank has the right flavor before Claude takes over.
"""

from __future__ import annotations

import sys
import time


BANNER = r"""
   ____ _                 _        ____
  / ___| | __ _ _   _  __| | ___  / ___|___  _ __ ___
 | |   | |/ _` | | | |/ _` |/ _ \| |   / _ \| '__/ _ \
 | |___| | (_| | |_| | (_| |  __/| |__| (_) | | |  __/
  \____|_|\__,_|\__,_|\__,_|\___(_)____\___/|_|  \___|
        C L A U D E C O R E . d l l   loaded
"""


def _line(text: str, delay: float) -> None:
    sys.stdout.write(text + "\n")
    sys.stdout.flush()
    if delay > 0:
        time.sleep(delay)


def play_injection(game_name: str, delay: float = 0.35) -> None:
    """Print the fake DLL-injection sequence."""
    print(BANNER)
    steps = [
        f"[ClaudeCore.dll] Attaching to process: {game_name} ...",
        "[ClaudeCore.dll] Allocating shadow memory ............... OK",
        "[ClaudeCore.dll] Resolving import table ................ OK",
        "[ClaudeCore.dll] Hooking render pipeline ............... OK",
        "[ClaudeCore.dll] Patching entity manager .............. OK",
        "[ClaudeCore.dll] Elevating cognition module ........... OK",
        "[ClaudeCore.dll] Handing control to C L A U D E ....... OK",
    ]
    for step in steps:
        _line(step, delay)
    _line("", delay)
