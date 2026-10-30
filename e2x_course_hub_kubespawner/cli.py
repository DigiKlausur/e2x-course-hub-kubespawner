"""Command line validator for a catalog configuration, e.g. before rolling out a change."""

import argparse
import sys
from pathlib import Path

from .errors import CatalogValidationError
from .loading import load_config, load_infrastructure_catalog


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="e2x-kubespawner-validate",
        description="Validate the infrastructure catalog of the e2x course hub kubespawner.",
    )
    parser.add_argument("config_file", type=Path, help="Path to the top-level config.yaml")
    args = parser.parse_args(argv)

    try:
        load_infrastructure_catalog(load_config(args.config_file))
    except CatalogValidationError as e:
        print(f"Catalog is invalid, {len(e.errors)} problem(s) found:\n", file=sys.stderr)
        for error in e.errors:
            print(f"- {error}\n", file=sys.stderr)
        return 1

    print("Catalog is valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
