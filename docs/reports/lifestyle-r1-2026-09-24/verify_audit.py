"""Offline entry point: verify original evidence and generated task reports."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
from paired_report import verify

if __name__ == "__main__":
    verify()
