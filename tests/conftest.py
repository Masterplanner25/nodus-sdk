"""pytest configuration for nodus-sdk tests."""

import sys
import os

# Ensure nodus-lang dev source takes priority
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "Coding Language", "src"))
