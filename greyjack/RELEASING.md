# Preparing and publishing GreyJack releases

GreyJack uses Maturin to prepare native wheels and source distributions. CI
builds and tests artifacts; publishing to PyPI is a separate manual action.
Run the commands below from the repository's `greyjack/` directory, using an
activated Python environment with Maturin 1.15.0 and `packaging` installed.
Rustup selects the repository's pinned Rust 1.98.1 toolchain.

## Release 0.3.9

- Python 3.10 is the minimum supported version. The wheel matrix covers CPython
  3.10, 3.11, 3.12, 3.13, and 3.14, using the ordinary GIL-enabled interpreters.
- Wheels target Linux x86_64 with glibc 2.28 or newer, Windows amd64, and macOS
  ARM64. Intel macOS is outside this release's wheel support: current releases
  of the mandatory Numba/llvmlite dependencies no longer provide Intel Mac wheels.
- The Python/native compatibility cohort is Python Polars `>=1.44.2,<1.45`,
  Rust Polars 0.55.2, pyo3-polars 0.28.0, and PyO3 0.29.2.
- Move generation validates variable bounds and preserves frozen and fixed
  variables. Regression tests cover integer, floating-point, and mixed domains.
- Agent failures reach callers as `RuntimeError`; normal stopping returns the
  best available solution or `None`, and Ctrl-C cleanup re-raises
  `KeyboardInterrupt`. Spawned workers require importable callbacks and a main
  guard; thread callbacks stop cooperatively.
- The original employee scoring example now uses real shift ends and calendar
  start dates, with construction errors propagated to the caller.

## What CI prepares

Every configured branch/pull-request run and every manual workflow dispatch prepares and
tests the artifacts without uploading to PyPI or creating a GitHub release.
The configured matrix builds 15 wheels: five Python versions on three platforms.
Each wheel uses `--release --strip --locked`; Linux builds run in a
`manylinux_2_28` container. CI uses ThinLTO, 16 codegen units, no debug information,
and two build jobs to reduce memory use on hosted runners while retaining
optimization level 3. These overrides leave local Cargo release settings intact.

Each job installs its wheel with fresh dependency resolution, runs `pip check`,
validates archive contents and metadata, and runs all core Python tests from
outside the checkout. Import checks reject accidentally imported checkout
sources. A separate Rust job runs the native unit tests with Python linking
enabled, without the extension-module feature used for wheel builds.

One authoritative source-distribution job creates the source archive, verifies
its Cargo lockfile and source/license contents, extracts it outside the checkout,
builds a wheel from that extracted source with `--locked`, and tests the installed
result. This verification wheel is not part of the published 15-wheel matrix.

The `release-artifacts` workflow artifact collects exactly 15 wheels, one source
archive, and `inventory.json`. The inventory records package version, source
commit SHA, filename, size, platform/Python tags, and SHA-256 for every archive.
Per-job inventories are included for inspection. Validation rejects missing
native extensions, missing lifecycle code, editable-install `.pth` files,
absolute/traversing archive paths, unsupported wheel tags, and incorrect Python
or Polars requirements. Archive validation complements the installed-wheel
tests; it does not itself establish runtime correctness.

Only a pushed `v*` tag whose version matches both `pyproject.toml` and `Cargo.toml`
can attach the tested wheels, source archive, and inventory to a GitHub release.
For this version the tag is `v0.3.9`. Tagging still does not upload anything to
PyPI. Inspect the completed workflow for the exact source commit before using
its artifacts; workflow configuration alone is not a successful test result.

## Prepare a local build without publishing

Use a clean checkout of the intended release commit. An inventory records the
commit you supply; it does not prove that uncommitted local changes came from
that commit.

```bash
python -m pip install 'maturin==1.15.0' packaging
maturin build --release --strip --locked --sdist --compatibility pypi --out target/release-dist
python scripts/validate_artifacts.py target/release-dist \
  --version 0.3.9 --commit "$(git rev-parse HEAD)" \
  --output target/release-dist/inventory.json
```

In Maturin 1.15, `--sdist` also builds the wheel from the source distribution,
checking that it contains the build inputs. `--strip` removes native debug
symbols from the packaged library; an editable development build can contain a
much larger unstripped binary. `--locked` requires the checked-in Cargo lockfile.
`--compatibility pypi` validates that the wheel uses uploadable platform tags.

This command prepares artifacts for the current host and installed interpreter.
It does not build the other operating systems' wheels. A Linux host with newer
glibc may produce a narrower manylinux tag than CI's glibc 2.28 baseline. Use the
tested CI collection for the complete supported release matrix. Preparing and
validating files does not publish them.

## Publish the exact tested CI files

Choose a successful workflow run for the intended commit. With GitHub CLI
authenticated, replace `RUN_ID` with that run's numeric ID and download its
`release-artifacts` artifact into a fresh directory:

```bash
gh run download RUN_ID --name release-artifacts --dir target/ci-release-dist
release_commit="$(gh run view RUN_ID --json headSha --jq .headSha)"
python scripts/validate_artifacts.py target/ci-release-dist --complete \
  --version 0.3.9 --commit "$release_commit" \
  --verify-inventory target/ci-release-dist/inventory.json
```

Review the version, commit, completed matrix tests, and inventory. Configure
Maturin's PyPI credentials securely, for example with `MATURIN_PYPI_TOKEN` in the
publishing process's environment. When intentionally publishing, upload the
validated archives themselves:

```bash
maturin upload --non-interactive target/ci-release-dist/*.whl target/ci-release-dist/*.tar.gz
```

This is the primary release path because it uploads the same bytes that passed
CI. The JSON inventories are review records and are not Python distributions.
The workflow contains no PyPI upload step and does not require a PyPI token.

## Direct host publishing

Maturin's normal build-and-publish command remains available for an intentional
manual host release:

```bash
maturin publish --locked --compatibility pypi
```

It builds in release mode, strips the library by default, creates the host's
wheel and a source distribution, and uploads them. It cannot produce the other
operating systems' wheels on that host, and it rebuilds files rather than
uploading the exact tested CI collection. Use the artifact-upload path above
when releasing the full supported matrix.
