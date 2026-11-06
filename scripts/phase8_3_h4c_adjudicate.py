#!/usr/bin/env python3
"""H4C read-only native Retry adjudication; never reads old H4B artifacts."""
import phase8_3_h4b_adjudicate as source
if __name__ == "__main__":
    source.configure_for_case("h4c_missing_read")
    source.main()
