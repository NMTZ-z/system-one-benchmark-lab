#!/usr/bin/env python3
"""Native H4D in-process Hermes child using pinned, credential-free source.

Requires exact original isolated run and HERMES_HOME; loader code is pulled
from a frozen audited Git archive, never installed production Hermes checkout.
The official installed Hermes venv Python is only the interpreter/libs.
"""
from __future__ import annotations
from pathlib import Path
import phase8_3_h4b_direct_child as native

if __name__ == "__main__":
    native.configure_for_case("h4d_missing_read")
    native.HERMES_INSTALL = Path(__file__).resolve().parents[1] / "private/phase8_3_native_real/h4d_hermes_archive"
    native.main()
