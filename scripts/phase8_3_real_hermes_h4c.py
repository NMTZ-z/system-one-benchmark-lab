#!/usr/bin/env python3
"""H4C separately frozen candidate; shared audited implementation, NEW run.

No new paid task without --execute-real-step-plan and exact frozen SHA.
This wrapper runs in a fresh parent process, and scopes the recovery and
owned-process ledgers to H4C (NOT old H4B).
"""
from __future__ import annotations
import phase8_3_real_hermes_h4b as runner

if __name__ == "__main__":
    runner.configure_for_case("h4c_missing_read")
    runner.main()
