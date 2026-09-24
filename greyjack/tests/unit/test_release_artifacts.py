"""Malformed and incomplete artifacts must fail before they can be released."""

import importlib.util
import io
import json
import tarfile
import zipfile
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "validate_artifacts.py"
SPEC = importlib.util.spec_from_file_location("release_artifact_validator", SCRIPT)
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)
VERSION = "0.3.9"
COMMIT = "a" * 40
METADATA = (
    "Metadata-Version: 2.4\nName: greyjack\nVersion: 0.3.9\n"
    "Requires-Python: >=3.10\nRequires-Dist: polars>=1.44.2,<1.45\n"
    "Requires-Dist: numba>=0.63\n\n"
)


def make_wheel(
    directory, python="cp312", platform="manylinux_2_28_x86_64", changes=None
):
    tag = f"{python}-{python}-{platform}"
    path = directory / f"greyjack-{VERSION}-{tag}.whl"
    suffix = ".pyd" if platform == "win_amd64" else ".so"
    files = {name: b"# Python source\n" for name in validator.PACKAGE_FILES}
    files[f"greyjack/greyjack.{python}{suffix}"] = b"native extension fixture"
    files[f"greyjack-{VERSION}.dist-info/METADATA"] = METADATA.encode()
    files[f"greyjack-{VERSION}.dist-info/WHEEL"] = (
        f"Wheel-Version: 1.0\nRoot-Is-Purelib: false\nTag: {tag}\n"
    ).encode()
    for name, contents in (changes or {}).items():
        if contents is None:
            files.pop(name)
        else:
            files[name] = contents
    with zipfile.ZipFile(path, "w") as archive:
        for name, contents in files.items():
            archive.writestr(name, contents)
    return path


def make_sdist(directory, missing=(), extra=None):
    path = directory / f"greyjack-{VERSION}.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        for relative in sorted(validator.SDIST_FILES - set(missing)):
            contents = METADATA.encode() if relative == "PKG-INFO" else b"source\n"
            info = tarfile.TarInfo(f"greyjack-{VERSION}/{relative}")
            info.size = len(contents)
            archive.addfile(info, io.BytesIO(contents))
        if extra is not None:
            archive.addfile(extra)
    return path


@pytest.mark.parametrize(
    "platform", ["manylinux_2_28_x86_64", "win_amd64", "macosx_11_0_arm64"]
)
def test_wheel_filename_metadata_and_native_layout(tmp_path, platform):
    path = make_wheel(tmp_path, platform=platform)
    result = validator.validate_wheel(path, VERSION, python="3.12")
    assert result["python"] == "cp312"
    assert result["platform"] in ("linux", "windows", "macos")


@pytest.mark.parametrize(
    "unsafe", ["/absolute.py", "../outside.py", "C:/source.py", "editable.pth"]
)
def test_wheel_rejects_absolute_traversal_and_editable_paths(tmp_path, unsafe):
    path = make_wheel(tmp_path, changes={unsafe: b"source"})
    with pytest.raises(ValueError, match="archive path|Editable-install"):
        validator.validate_wheel(path, VERSION)


@pytest.mark.parametrize(
    "missing",
    ["greyjack/greyjack.cp312.so", "greyjack/agents/base/_lifecycle.py"],
)
def test_wheel_requires_native_library_and_lifecycle_source(tmp_path, missing):
    path = make_wheel(tmp_path, changes={missing: None})
    with pytest.raises(ValueError, match="native extension|missing GreyJack"):
        validator.validate_wheel(path, VERSION)


@pytest.mark.parametrize(
    "old,new,message",
    [
        ("Version: 0.3.9", "Version: 0.3.8", "Version mismatch"),
        (">=3.10", ">=3.9", "Requires-Python"),
        ("polars>=1.44.2,<1.45", "polars>=1.44.2", "Polars"),
        ("Requires-Dist: numba>=0.63\n", "", "Numba"),
    ],
)
def test_wheel_rejects_incorrect_dependency_metadata(tmp_path, old, new, message):
    path = make_wheel(
        tmp_path,
        changes={
            f"greyjack-{VERSION}.dist-info/METADATA": METADATA.replace(
                old, new
            ).encode()
        },
    )
    with pytest.raises(ValueError, match=message):
        validator.validate_wheel(path, VERSION)


def test_expected_python_platform_and_wheel_metadata_must_agree(tmp_path):
    path = make_wheel(tmp_path)
    with pytest.raises(ValueError, match="Python wheel tag"):
        validator.validate_wheel(path, VERSION, python="3.14")
    with pytest.raises(ValueError, match="wheel platform"):
        validator.validate_wheel(path, VERSION, platform="windows")
    path = make_wheel(
        tmp_path,
        changes={
            f"greyjack-{VERSION}.dist-info/WHEEL": b"Root-Is-Purelib: false\nTag: cp311-cp311-manylinux_2_28_x86_64\n"
        },
    )
    with pytest.raises(ValueError, match="tags disagree"):
        validator.validate_wheel(path, VERSION)


def test_sdist_requires_lockfile_and_extracts_validated_sources(tmp_path):
    path = make_sdist(tmp_path, missing={"Cargo.lock"})
    with pytest.raises(ValueError, match="Cargo.lock"):
        validator.validate_sdist(path, VERSION)
    path = make_sdist(tmp_path)
    destination = tmp_path / "extracted"
    validator.validate_sdist(path, VERSION, destination)
    assert (
        destination / f"greyjack-{VERSION}" / "Cargo.lock"
    ).read_bytes() == b"source\n"
    assert (
        destination / f"greyjack-{VERSION}" / "greyjack/agents/base/_lifecycle.py"
    ).is_file()


def test_sdist_rejects_links_before_writing_any_files(tmp_path):
    link = tarfile.TarInfo(f"greyjack-{VERSION}/escape")
    link.type = tarfile.SYMTYPE
    link.linkname = "/tmp/outside"
    path = make_sdist(tmp_path, extra=link)
    destination = tmp_path / "extracted"
    with pytest.raises(ValueError, match="links and special files"):
        validator.validate_sdist(path, VERSION, destination)
    assert not destination.exists()


def test_complete_inventory_requires_all_supported_wheels_and_one_sdist(tmp_path):
    paths = [make_sdist(tmp_path)]
    for python in sorted(validator.PYTHON_TAGS):
        for platform in ("manylinux_2_28_x86_64", "win_amd64", "macosx_11_0_arm64"):
            paths.append(make_wheel(tmp_path, python, platform))
    result = validator.inventory(paths, VERSION, COMMIT, complete=True)
    assert len(result["artifacts"]) == 16
    assert result["commit"] == COMMIT
    assert all(len(item["sha256"]) == 64 for item in result["artifacts"])
    with pytest.raises(ValueError, match="exactly 15 wheels"):
        validator.inventory(paths[:-1], VERSION, COMMIT, complete=True)
    with pytest.raises(ValueError, match="exactly one sdist"):
        validator.inventory(paths[1:], VERSION, COMMIT, complete=True)


def test_complete_linux_baseline_rejects_host_only_newer_glibc(tmp_path):
    path = make_wheel(tmp_path, platform="manylinux_2_39_x86_64")
    validator.validate_wheel(path, VERSION)
    with pytest.raises(ValueError, match="manylinux_2_28"):
        validator.validate_wheel(path, VERSION, platform="linux")


def test_inventory_verification_detects_changed_bytes_and_tag(tmp_path):
    path = make_wheel(tmp_path)
    saved = tmp_path / "inventory.json"
    args = [str(path), "--version", VERSION, "--commit", COMMIT]
    assert validator.main(args + ["--output", str(saved)]) == 0
    assert json.loads(saved.read_text())["artifacts"][0]["filename"] == path.name
    assert validator.main(args + ["--verify-inventory", str(saved)]) == 0
    with pytest.raises(SystemExit) as error:
        validator.main(args + ["--tag", "v0.3.8"])
    assert error.value.code == 2
    with zipfile.ZipFile(path, "a") as archive:
        archive.writestr("greyjack/extra.py", "changed bytes")
    with pytest.raises(SystemExit) as error:
        validator.main(args + ["--verify-inventory", str(saved)])
    assert error.value.code == 2
