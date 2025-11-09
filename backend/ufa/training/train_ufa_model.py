#!/usr/bin/env python3
"""
Simple wrapper to trigger UFA training
Calls the train_from_real_matches function from trainer.py
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ufa.training.trainer import train_from_real_matches

if __name__ == "__main__":
    print("🎓 Starting UFA training from real_scores.jsonl...")
    try:
        result = train_from_real_matches()
        print(f"✅ Training completed: {result}")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Training failed: {e}")
        sys.exit(1)
