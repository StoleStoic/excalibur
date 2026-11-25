# Excalibur

A private, fast, open-source web browser for Windows, built on Chromium.

Excalibur is a small set of patches and build settings applied on top of
[ungoogled-chromium](https://github.com/ungoogled-software/ungoogled-chromium)
(via [ungoogled-chromium-windows](https://github.com/ungoogled-software/ungoogled-chromium-windows),
pinned as a git submodule in `upstream/`). It is not a copy of the Chromium
source: each release is built from the official Chromium source plus the
patches in this repository, so every change Excalibur makes is reviewable.

## Status

Early. The project compiles and packages on GitHub Actions: the first full
build (Chromium 158.0.8127.36) produced an installer and a portable zip that
carry the Excalibur name and identity. That installer has not yet been
installed and exercised on a real Windows machine, and there is no signed
release.

## What you get

Inherited from ungoogled-chromium:

- No Google account sign-in, sync, AI features, Safe Browsing, field trials,
  crash or usage reporting, or background requests to Google.
- Third-party cookies blocked, link-click tracking (`ping`) off, page
  preloading off, search suggestions off, WebRTC limited so it does not leak
  your local IP address.
- Full Chromium DevTools, and Chrome extension support (load your own from
  `chrome://extensions` with Developer mode on).

Added by Excalibur (`patches/excalibur/`):

| Patch | What it does |
| --- | --- |
| `branding.patch` | Product and company name in the executable and installer. |
| `install-identity.patch` | Own install folder, profile folder, registry keys and file associations, so it installs next to Chromium without sharing data. |
| `default-privacy-prefs.patch` | Do Not Track on and HTTPS-Only Mode on by default. |

## Repository layout

| Path | Purpose |
| --- | --- |
| `upstream/ungoogled-chromium-windows` | Pinned upstream build system and patches (submodule). |
| `patches/series`, `patches/excalibur/` | Excalibur's patches, applied in order after upstream's. |
| `flags.excalibur.gn` | Build flags merged over upstream's. |
| `build.py` | Stages the merged tree, runs the upstream build, packages the result. |
| `devutils/check_patches.py` | Fast check that the patches apply to the pinned Chromium. |
| `.github/workflows/` | `check` (every PR), `build` (tags / manual), `upstream-update` (daily). |

## Building

Building Chromium needs Windows 10/11 x64, about 100 GB of free disk, 16 GB or
more of RAM, and several hours. Set up Visual Studio, the Windows SDK, 7-Zip,
Python and Git exactly as described in the
[upstream build instructions](upstream/ungoogled-chromium-windows/README.md#building),
then, in a *Developer Command Prompt for VS* run as administrator:

```cmd
git clone --recurse-submodules <this repository's URL>
cd excalibur
python -m pip install httplib2==0.22.0 clang==21.1.7
python build.py --stage-dir C:\ex --package
```

The installer and a portable zip are written to `dist\`. `--stage-dir` should
be a short path; the Chromium source and build output live under it and are
kept between runs.

Without a Windows machine: push a tag (or run the `build` workflow manually)
and GitHub Actions builds it in resumable stages, then attaches the installer
to a release.

## Changing the browser

1. Run `python devutils/check_patches.py --prepare-only`. This creates
   `build/check_patches/tree` containing the files the existing patches touch,
   as they look after upstream's patches. For a file not in there yet,
   download it from the Chromium tag in
   `upstream/ungoogled-chromium-windows/ungoogled-chromium/chromium_version.txt`.
2. Copy the tree, edit the copy, and save `diff -u` output (with `a/` and `b/`
   path prefixes) as `patches/excalibur/<name>.patch`.
3. Add the patch to `patches/series`.
4. Run `python devutils/check_patches.py`.

Keep patches small and single-purpose; every patch is a recurring cost each
time Chromium updates.

## Staying secure

Most of a browser's security is how quickly it ships Chromium's fixes, which
arrive roughly weekly. The `upstream-update` workflow opens a pull request for
each new upstream release and reports whether the patches still apply. Merge
it, push a tag, and a release is built. Treat a stale release as a security
bug.

## Roadmap

In rough priority order:

1. **Install and smoke-test the first build** on Windows; publish a first release.
2. **Automatic updates.** Upstream has no updater. Until Excalibur has one,
   users must install each new version by hand, which is not acceptable for
   non-technical users.
3. **Code signing.** Unsigned installers trigger Windows SmartScreen warnings.
4. **Built-in ad and tracker blocking.** Upstream has none. Options are
   bundling a Manifest V3 content blocker as a built-in extension, or
   integrating a network-level blocking engine.
5. **Simple controls panel:** one page of plain-language on/off switches
   (ads, trackers, cookies, JavaScript, WebRTC, password saving, developer
   mode) for people who should never need `chrome://flags`.
6. **Finish the rebrand:** user-visible strings and icons still say Chromium.
   Give the elevation and tracing services their own COM identifiers.
7. **Decide on defaults upstream turns off:** password saving and autofill are
   off, and there is no phishing/malware protection because Safe Browsing
   depends on Google. Both are usability and security trade-offs worth
   revisiting for a non-technical audience.
8. **Extension installs.** Extensions you build load today; installing from
   the Chrome Web Store does not work out of the box.

## License

BSD 3-Clause; see [LICENSE](LICENSE). Chromium and ungoogled-chromium are
covered by their own licenses.
