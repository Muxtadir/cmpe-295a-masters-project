"""
Previously inserted synthetic ``seed_demo`` sales and DEMO-SKU inventory.

Demo sales are removed from the project: use Kaggle data only.

  PYTHONPATH=. python scripts/load_kaggle_dataset.py --replace --max-rows 1500000

To drop any leftover demo sales from an old DB:

  PYTHONPATH=. python scripts/load_kaggle_dataset.py --replace --clear-seed-demo --max-rows 1500000

This script is a no-op (exit 0) so existing docs/commands do not fail.
"""

from __future__ import annotations


def main() -> None:
    print(
        "seed_demo.py: demo seeding disabled. "
        "Load real data with scripts/load_kaggle_dataset.py (see module docstring)."
    )


if __name__ == "__main__":
    main()
