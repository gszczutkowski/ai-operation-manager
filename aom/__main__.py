"""Allow running as `python -m aom`."""
import sys
from .cli import main

sys.exit(main())
