"""Print one value from config/environments/<env>.yaml (with MDAA_* env-var overrides), for CI steps.
    python scripts/env_value.py --env cevo-aws-mcds aws.region
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_mdaa import load_env, lookup  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--env", required=True)
ap.add_argument("key")
a = ap.parse_args()
v = lookup(load_env(a.env), a.key)
print(str(v).lower() if isinstance(v, bool) else v)
