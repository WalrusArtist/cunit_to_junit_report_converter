# Copyright (c) 2026 Kardo Marof. All rights reserved.
#
# This source code is licensed under the AGPL-3.0 license found in the
# LICENSE file in the root directory of this source tree.

"""Command-line interface for CUnit to JUnit XML converter."""

import argparse
import logging
import sys
from pathlib import Path

from cunit_to_junit.converter import cunit_to_junit


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert CUnit XML reports to JUnit XML format.",
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to the CUnit XML input file.",
    )
    parser.add_argument(
        "output",
        type=Path,
        help="Path for the JUnit XML output file.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if not args.input.exists():
        logging.error(f"Input file not found: {args.input}")
        sys.exit(1)

    cunit_to_junit(args.input, args.output)


if __name__ == "__main__":
    main()
