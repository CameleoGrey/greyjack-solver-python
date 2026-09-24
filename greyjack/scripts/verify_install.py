"""Check that release tests import the installed distribution, not checkout code."""

import argparse
from importlib import import_module, metadata
from pathlib import Path

from packaging.specifiers import SpecifierSet
from packaging.version import Version


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--checkout", required=True, type=Path)
    args = parser.parse_args(argv)
    checkout = args.checkout.resolve()
    for name in ("greyjack", "greyjack.greyjack", "greyjack.agents.base._lifecycle"):
        module = import_module(name)
        path = Path(module.__file__).resolve()
        if checkout == path or checkout in path.parents:
            parser.error(f"Imported checkout source instead of installed wheel: {path}")
        print(f"{name}: {path}")
    if Version(metadata.version("greyjack")) != Version(args.version):
        parser.error("Installed GreyJack version does not match the release")
    if Version(metadata.version("polars")) not in SpecifierSet(">=1.44.2,<1.45"):
        parser.error("Installed Polars is outside the supported compatibility range")
    print(
        f"GreyJack {metadata.version('greyjack')}; Polars {metadata.version('polars')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
