# Foundry Model Router Evaluation Toolkit

from __future__ import annotations

import sys


def configure_console_encoding() -> None:
    """Best-effort: ensure stdout/stderr can encode Unicode (e.g. ✓, ─, ▏).

    On Windows, the default console encoding is often cp1252 which can't encode
    common output characters. Calling this from CLI entry points avoids
    ``UnicodeEncodeError`` crashes on default Windows shells.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                # Some environments (e.g. captured streams) don't support reconfigure
                pass
