# Vendored RISC-V Wheels dashboard generator

This directory is a **vendored copy** of the dashboard generator from
<https://github.com/riseproject-dev/python-wheels-dashboard>, used to publish the
dashboard at <https://pypi.riseproject.dev/dashboard/> as part of this repo's
website build (`.github/workflows/website.yml`, `deploy` job).

The dashboard repo remains the **upstream source of truth**. It keeps its own
GitHub Pages site and its own 6-hourly refresh; this copy is regenerated on each
publish from `main`. The two sites can legitimately disagree by a few hours.

Vendored from commit **`edcf127`** ("Persist pypi.org request cache across CI
runs, pin actions to SHAs").

## Licensing

The upstream project is BSD-2-Clause, whose clause 1 requires retaining the
copyright notice, so `LICENSE` is shipped verbatim and the vendored files carry
BSD-2-Clause SPDX headers. Only `build.py` is RISE-authored and MIT, matching the
rest of this repo.

## Files

| File | Origin |
|---|---|
| `LICENSE` | verbatim from upstream |
| `generate.py`, `utils.py`, `svg_wheel.py` | upstream, SPDX header prepended |
| `wheel.css`, `favicon.ico` | verbatim from upstream |
| `index.html` | upstream, with the text edits listed below |
| `build.py` | **new**, RISE-authored — not upstream |

The generator's own dependencies (`requests`, `requests-cache`) live in
`ci_scripts/requirements.txt` alongside the rest of this repo's CI Python deps;
upstream's `pre-commit` pin is dropped, as there are no local hooks here.

`build.py` holds all python-wheels-specific logic so that the upstream files stay
a clean copy. It fetches and sanity-checks the package list, runs `generate.py` in
a scratch directory, validates the result, and only then stages five files into
the Jekyll source tree.

## Resyncing from upstream

```bash
cd ci_scripts/dashboard
UP=/path/to/python-wheels-dashboard
cp "$UP"/{LICENSE,generate.py,utils.py,svg_wheel.py,index.html,wheel.css,favicon.ico} .
```

Then re-apply the local deltas:

1. Prepend the BSD-2-Clause SPDX header to `generate.py`, `utils.py` and
   `svg_wheel.py` (copy it from a sibling file).
2. Re-apply the `index.html` edits:
   - drop the stale "top 360" figure from the "What is this list?" paragraph and
     the "Thanks" paragraph — the generator applies no slice, so the real count
     moves every run;
   - change the footer cadence from "Updated daily." to the real cadence;
   - keep the absolute link back to <https://pypi.riseproject.dev/> near the `<h1>`.
3. If upstream changed its `requests`/`requests-cache` pins, update them in
   `ci_scripts/requirements.txt`.
4. Update the vendored commit SHA above.

Leave `build.py` alone — it is not upstream.

**Never add YAML front matter to `index.html`.** It contains AngularJS bindings
(`{{ package.name }}`) that are also valid Liquid. The file is correct only
because Jekyll treats it as a static file and copies it byte-for-byte; front
matter would make Liquid eat the bindings and the package list would render empty
with no build error. `build.py` asserts this.

## Running it locally

```bash
pip install -r ../requirements.txt
python build.py --build-dir /tmp/dash --output-dir ../../docs/dashboard
```

A cold run makes one pypi.org request per package (~15000 at 8 concurrency) and
writes a multi-GB `requests-cache.sqlite` into the build dir, which is why the
build dir is kept outside `docs/`.
