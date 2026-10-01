# SPDX-FileCopyrightText: 2013 Charlie Denton
# SPDX-FileCopyrightText: 2026 Stan Ulbrych
# SPDX-License-Identifier: BSD-2-Clause
#
# Vendored from riseproject-dev/python-wheels-dashboard. See README.md.

from svg_wheel import generate_svg_wheel
from utils import (
    annotate_wheels,
    get_top_packages,
    save_to_file,
)


def main() -> None:
    packages = get_top_packages()
    packages = annotate_wheels(packages)
    save_to_file(packages, "results.json")
    generate_svg_wheel(packages)


if __name__ == "__main__":
    main()
