#!/usr/bin/env python3
"""H4C independent case-specific official Hermes in-process read-only child.

The actual implementation is the verified generic H4B security boundary,
explicitly rebound to a brand-new H4C case inside THIS child process.
Never reuses the previous H4B manifest or Session evidence.
"""
from __future__ import annotations
import phase8_3_h4b_direct_child as native

if __name__ == "__main__":
    native.configure_for_case("h4c_missing_read")
    native.main()
