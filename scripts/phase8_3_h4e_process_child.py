"""Do not execute the child command until the parent has fsynced its identity."""
import os
import sys

if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.stdin.readline().strip() != 'H4E_PARENT_GO':
        raise SystemExit(3)
    os.execv(sys.argv[1], sys.argv[1:])
