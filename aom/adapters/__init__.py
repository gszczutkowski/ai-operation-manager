"""
Structure adapters — detect and extract SkillRecords from different on-disk layouts.

Registered adapters are tried in priority order for every path encountered:
  1. SuffixAdapter   — Option A: name@version/  or  name@version.md
  2. DirAdapter      — Option B: name/1.0.0/    or  name/1.0.0.md
  3. MetadataAdapter — Option C: name/ or name.md, version in frontmatter  ← recommended
"""
from .suffix_adapter import SuffixAdapter
from .dir_adapter import DirAdapter
from .metadata_adapter import MetadataAdapter

# Order matters: highest priority first (suffix > directory > metadata)
ADAPTERS = [SuffixAdapter(), DirAdapter(), MetadataAdapter()]

__all__ = ["SuffixAdapter", "DirAdapter", "MetadataAdapter", "ADAPTERS"]
