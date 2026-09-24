"""Validate release archives and record their exact bytes; never build or upload."""

import argparse
import hashlib
import json
import re
import shutil
import tarfile
import zipfile
from email.parser import BytesParser
from pathlib import Path, PurePosixPath

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.tags import parse_tag
from packaging.utils import (
    canonicalize_name,
    parse_sdist_filename,
    parse_wheel_filename,
)
from packaging.version import Version


PYTHON_TAGS = {f"cp3{minor}" for minor in range(10, 15)}
PLATFORMS = {"linux", "windows", "macos"}
PACKAGE_FILES = {
    "greyjack/__init__.py",
    "greyjack/SolverOOP.py",
    "greyjack/agents/base/_lifecycle.py",
}
SDIST_FILES = PACKAGE_FILES | {
    "Cargo.toml",
    "Cargo.lock",
    "pyproject.toml",
    "src/lib.rs",
    "LICENSE",
    "LICENSES-third-party/LICENSE-Polars.txt",
    "LICENSES-third-party/LICENSE-pyzmq.txt",
    "PKG-INFO",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe_member(name):
    path = PurePosixPath(name)
    require(
        name
        and path.parts
        and not path.is_absolute()
        and ".." not in path.parts
        and "\\" not in name
        and not re.match(r"^[A-Za-z]:", name),
        f"Unsafe archive path: {name!r}",
    )
    require(
        path.suffix.lower() != ".pth" and "__editable__" not in name,
        f"Editable-install file in release archive: {name}",
    )
    return path


def check_metadata(data, version):
    metadata = BytesParser().parsebytes(data)
    require(
        canonicalize_name(metadata.get("Name", "")) == "greyjack", "Wrong package name"
    )
    require(
        Version(metadata.get("Version", "0")) == Version(version), "Version mismatch"
    )
    require(
        SpecifierSet(metadata.get("Requires-Python", "")) == SpecifierSet(">=3.10"),
        "Requires-Python must be >=3.10",
    )
    requirements = [
        Requirement(value) for value in metadata.get_all("Requires-Dist", [])
    ]
    polars = [item for item in requirements if canonicalize_name(item.name) == "polars"]
    require(
        len(polars) == 1
        and polars[0].marker is None
        and polars[0].specifier == SpecifierSet(">=1.44.2,<1.45"),
        "Polars must be an unconditional >=1.44.2,<1.45 dependency",
    )
    numba = [item for item in requirements if canonicalize_name(item.name) == "numba"]
    require(
        len(numba) == 1 and numba[0].marker is None,
        "Numba must remain a mandatory dependency",
    )


def platform_family(platform):
    if re.fullmatch(r"manylinux_\d+_\d+_x86_64", platform):
        return "linux"
    if platform == "win_amd64":
        return "windows"
    if re.fullmatch(r"macosx_\d+_\d+_arm64", platform):
        return "macos"
    raise ValueError(f"Unsupported wheel platform tag: {platform}")


def validate_wheel(path, version, python=None, platform=None):
    name, parsed_version, _, tags = parse_wheel_filename(path.name)
    require(
        name == "greyjack" and parsed_version == Version(version),
        "Wrong wheel filename/version",
    )
    interpreters = {tag.interpreter for tag in tags}
    require(
        len(interpreters) == 1 and interpreters <= PYTHON_TAGS,
        "Expected CPython 3.10-3.14 wheel",
    )
    require(
        all(tag.abi == tag.interpreter for tag in tags), "Expected CPython-specific ABI"
    )
    if python is not None:
        require(
            interpreters == {"cp" + python.replace(".", "")}, "Wrong Python wheel tag"
        )
    families = {platform_family(tag.platform) for tag in tags}
    require(len(families) == 1, "Mixed wheel platform families")
    family = next(iter(families))
    if platform is not None:
        require(family == platform, "Wrong wheel platform")
        if platform == "linux":
            require(
                {tag.platform for tag in tags} == {"manylinux_2_28_x86_64"},
                "Linux release wheels must target manylinux_2_28_x86_64",
            )

    with zipfile.ZipFile(path) as archive:
        members = archive.namelist()
        require(len(members) == len(set(members)), "Duplicate wheel archive paths")
        for member in members:
            safe_member(member)
        require(
            PACKAGE_FILES <= set(members), "Wheel is missing GreyJack Python sources"
        )
        native_suffix = ".pyd" if family == "windows" else ".so"
        native = [
            member
            for member in members
            if member.startswith("greyjack/greyjack") and member.endswith(native_suffix)
        ]
        require(
            len(native) == 1 and archive.getinfo(native[0]).file_size > 0,
            "Wheel needs one native extension",
        )
        metadata_paths = [
            member for member in members if member.endswith(".dist-info/METADATA")
        ]
        require(len(metadata_paths) == 1, "Wheel needs exactly one METADATA file")
        check_metadata(archive.read(metadata_paths[0]), version)
        wheel_path = metadata_paths[0].removesuffix("METADATA") + "WHEEL"
        require(wheel_path in members, "Wheel is missing WHEEL metadata")
        wheel = BytesParser().parsebytes(archive.read(wheel_path))
        require(
            wheel.get("Root-Is-Purelib", "").lower() == "false",
            "Native wheel marked pure Python",
        )
        declared_tags = set().union(
            *(parse_tag(tag) for tag in wheel.get_all("Tag", []))
        )
        require(declared_tags == tags, "WHEEL tags disagree with filename")
    return {
        "kind": "wheel",
        "python": next(iter(interpreters)),
        "platform": family,
        "tags": sorted(str(tag) for tag in tags),
    }


def validate_sdist(path, version, extract_to=None):
    name, parsed_version = parse_sdist_filename(path.name)
    require(
        name == "greyjack" and parsed_version == Version(version),
        "Wrong sdist filename/version",
    )
    root = f"greyjack-{version}"
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        require(len(names) == len(set(names)), "Duplicate sdist archive paths")
        for member in members:
            parts = safe_member(member.name).parts
            require(parts[0] == root, "Unexpected sdist root directory")
            require(
                member.isdir() or member.isfile(),
                "Sdist links and special files are forbidden",
            )
            require(not member.name.endswith((".so", ".pyd")), "Native binary in sdist")
        relative = {str(PurePosixPath(name).relative_to(root)) for name in names}
        require(
            SDIST_FILES <= relative,
            f"Sdist missing required files: {sorted(SDIST_FILES - relative)}",
        )
        metadata = archive.extractfile(f"{root}/PKG-INFO")
        require(metadata is not None, "Sdist PKG-INFO is not a file")
        check_metadata(metadata.read(), version)
        if extract_to is not None:
            extract_to.mkdir(parents=True, exist_ok=False)
            for member in members:
                target = extract_to.joinpath(*PurePosixPath(member.name).parts)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    source = archive.extractfile(member)
                    with source, target.open("wb") as destination:
                        shutil.copyfileobj(source, destination)
    return {"kind": "sdist"}


def artifact_paths(inputs):
    paths = []
    for item in inputs:
        if item.is_dir():
            paths.extend(item.rglob("*.whl"))
            paths.extend(item.rglob("*.tar.gz"))
        else:
            require(item.is_file(), f"Artifact not found: {item}")
            paths.append(item)
    require(bool(paths), "No release archives found")
    require(
        len({path.name for path in paths}) == len(paths), "Duplicate artifact filenames"
    )
    return sorted(paths, key=lambda path: path.name)


def inventory(paths, version, commit, python=None, platform=None, complete=False):
    require(
        re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", commit),
        "Commit must be a full Git SHA",
    )
    records = []
    for path in paths:
        if path.suffix == ".whl":
            details = validate_wheel(path, version, python, platform)
            if complete:
                validate_wheel(path, version, platform=details["platform"])
        else:
            require(path.name.endswith(".tar.gz"), f"Unsupported release file: {path}")
            details = validate_sdist(path, version)
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        records.append(
            {
                "filename": path.name,
                "size": path.stat().st_size,
                "sha256": digest.hexdigest(),
                **details,
            }
        )
    if complete:
        wheels = [record for record in records if record["kind"] == "wheel"]
        expected = {
            (python_tag, family) for python_tag in PYTHON_TAGS for family in PLATFORMS
        }
        require(
            len(wheels) == 15
            and {(item["python"], item["platform"]) for item in wheels} == expected,
            "Release needs exactly 15 wheels: CPython 3.10-3.14 on Linux x86_64, Windows amd64, macOS ARM64",
        )
        require(
            sum(record["kind"] == "sdist" for record in records) == 1,
            "Release needs exactly one sdist",
        )
    return {
        "schema_version": 1,
        "package": "greyjack",
        "version": version,
        "commit": commit.lower(),
        "artifacts": records,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "artifacts",
        nargs="+",
        type=Path,
        help="Archives or directories containing them",
    )
    parser.add_argument(
        "--version", required=True, help="Expected release version, for example 0.3.9"
    )
    parser.add_argument("--commit", required=True, help="Full source Git commit SHA")
    parser.add_argument("--tag", help="Optional release tag; must equal v<version>")
    parser.add_argument("--python", choices=[f"3.{minor}" for minor in range(10, 15)])
    parser.add_argument("--platform", choices=sorted(PLATFORMS))
    parser.add_argument(
        "--complete", action="store_true", help="Require all 15 wheels and one sdist"
    )
    parser.add_argument("--output", type=Path, help="Write SHA-256 inventory JSON")
    parser.add_argument(
        "--verify-inventory",
        type=Path,
        help="Compare exact bytes against an existing inventory",
    )
    parser.add_argument(
        "--extract-sdist",
        type=Path,
        help="Extract one validated sdist into a new directory",
    )
    args = parser.parse_args(argv)
    try:
        if args.tag is not None:
            require(
                args.tag == f"v{args.version}",
                "Release tag and package version disagree",
            )
        paths = artifact_paths(args.artifacts)
        result = inventory(
            paths, args.version, args.commit, args.python, args.platform, args.complete
        )
        if args.verify_inventory is not None:
            require(
                json.loads(args.verify_inventory.read_text(encoding="utf-8")) == result,
                "Inventory does not match the artifact bytes or source commit",
            )
        if args.extract_sdist is not None:
            require(
                len(paths) == 1 and paths[0].name.endswith(".tar.gz"),
                "Extraction requires exactly one sdist",
            )
            validate_sdist(paths[0], args.version, args.extract_sdist)
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(result, indent=2) + "\n", encoding="utf-8"
            )
        print(
            f"Validated {len(paths)} release archive(s) for GreyJack {args.version} at {args.commit}"
        )
    except (
        OSError,
        ValueError,
        KeyError,
        tarfile.TarError,
        zipfile.BadZipFile,
    ) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
