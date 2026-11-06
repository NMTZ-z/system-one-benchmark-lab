#!/usr/bin/env python3
"""H4D independent read-only original Hermes tool/Retry and Step Plan audit.

No native Agent or Provider calls. H4D alone, never reuse H4B/C output.
"""
from __future__ import annotations
import phase8_3_h4b_adjudicate as source
if __name__ == "__main__":
    source.configure_for_case("h4d_missing_read")
    source.main()
