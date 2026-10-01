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
| `svg_wheel.py` | upstream, SPDX header prepended |
| `utils.py` | upstream, SPDX header prepended, plus the registry change below |
| `wheel.css`, `favicon.ico` | verbatim from upstream |
| `index.html` | upstream, with the text edits listed below |
| `build.py` | **new**, RISE-authored — not upstream |

Upstream's `generate.py` is **not** vendored: it is a four-line `main()`, and
`build.py` calls those same four functions itself.

The generator's own dependencies (`requests`, `requests-cache`) live in
`ci_scripts/requirements.txt` alongside the rest of this repo's CI Python deps;
upstream's `pre-commit` pin is dropped, as there are no local hooks here.

`build.py` holds all python-wheels-specific logic. It fetches and sanity-checks the
package list, collects the registry contents from `docs/packages/*.yaml`, imports
`utils` and `svg_wheel` to produce `results.json` and `wheel.svg` in a scratch
directory, validates the result, and only then stages five files into the Jekyll
source tree.

Because it imports the vendored modules rather than spawning them, two cwd-bound
details matter. `utils` builds its `CachedSession` from a relative path **at import
time**, and `get_top_packages()`/`generate_svg_wheel()` read and write relative to
the cwd. So `build.py` resolves its path arguments to absolute, `chdir`s into the
build dir, and rebinds `utils.SESSION` there — otherwise a multi-GB
`requests-cache.sqlite` lands wherever the script was invoked from.

## The registry lookup

Upstream's `utils.in_rise_registry()` asks
`https://pypi.riseproject.dev/simple/<name>/` whether the registry has a package,
one HTTP request per candidate. In this repo the answer is already on disk:
`docs/packages/*.yaml` is what the registry index is generated from, and
`generate_packages_doc.py` publishes that index in the same job that builds this
dashboard — so the HTTP answer is a deploy behind, and `requests-cache` can pin a
404 for a newly added package for up to 30 days.

So `in_rise_registry()` is gone, along with `RISE_REGISTRY_URL`, and
`annotate_wheels(packages, registry)` takes the set of normalised names that
`build.py` collected and tests membership directly.

## Resyncing from upstream

```bash
cd ci_scripts/dashboard
UP=/path/to/python-wheels-dashboard
cp "$UP"/{LICENSE,utils.py,svg_wheel.py,index.html,wheel.css,favicon.ico} .
```

Then re-apply the local deltas:

1. Prepend the BSD-2-Clause SPDX header to `utils.py` and `svg_wheel.py` (copy it
   from a sibling file).
2. Re-apply the registry change described above: drop `RISE_REGISTRY_URL` and
   `in_rise_registry()`, give `annotate_wheels()` a `registry` parameter, and use
   `normalize(package["name"]) in registry` where the HTTP probe was.
3. Re-apply the `index.html` edits:
   - drop the stale "top 360" figure from the "What is this list?" paragraph and
     the "Thanks" paragraph — the generator applies no slice, so the real count
     moves every run;
   - change the footer cadence from "Updated daily." to the real cadence;
   - keep the absolute link back to <https://pypi.riseproject.dev/> near the `<h1>`.
4. If upstream changed its `requests`/`requests-cache` pins, update them in
   `ci_scripts/requirements.txt`.
5. If upstream's `generate.py` grew a step beyond its four calls, mirror it in
   `build.py`'s `main()`.
6. Update the vendored commit SHA above.

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
