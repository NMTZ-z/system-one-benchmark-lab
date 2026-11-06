#!/usr/bin/env python3
"""Only a NEW H4C scratch ephemeral rehearsal, never H4B original."""
import json
import phase8_3_h4b_offline_rehearsal as rehearsal

if __name__=="__main__":
    print(json.dumps(rehearsal.run(case_id="h4c_missing_read"),
                     sort_keys=True,indent=2))
