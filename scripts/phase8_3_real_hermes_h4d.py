#!/usr/bin/env python3
"""Separately approved one-shot real H4D only, physical Step Plan cap 3/90 s.

New H4D distinct from H4/H4B/H4C; no old evidence deletion/replay.
Exact safety, durable rollback and physical limits live in shared audited
runner but are bound to h4d_missing_read in this isolated process only.
No execution without --execute-real-step-plan and exact frozen SHA.
"""
from __future__ import annotations
import phase8_3_real_hermes_h4b as runner

if __name__ == "__main__":
    runner.configure_for_case("h4d_missing_read")
    runner.main()
