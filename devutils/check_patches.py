#!/usr/bin/env python3
# Copyright (c) 2026 The Excalibur Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""
Checks that Excalibur's patches still apply to the pinned Chromium version,
without downloading the full source tree.

For every file our patches touch, this downloads that one file at the pinned
Chromium tag, applies the upstream (ungoogled-chromium) changes to it in series
order, then applies our patches with no fuzz. It takes seconds, so it runs on
every pull request and on every upstream update.

It proves the patches apply. It does not prove the result compiles.

Requires the `patch` program (GNU patch).
"""

import argparse
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UPSTREAM_WINDOWS = ROOT / 'upstream' / 'ungoogled-chromium-windows'
UPSTREAM_CORE = UPSTREAM_WINDOWS / 'ungoogled-chromium'
SOURCE_URL = 'https://raw.githubusercontent.com/chromium/chromium/{version}/{path}'
ENCODING = 'UTF-8'

sys.path.insert(0, str(ROOT))
from build import read_series  # pylint: disable=wrong-import-position
sys.path.pop(0)


def split_patch(text):
    """Yields (target_path, file_diff_text, creates_file) per file in a patch."""
    lines = text.splitlines(keepends=True)
    starts = [
        i for i in range(len(lines) - 1)
        if lines[i].startswith('--- ') and lines[i + 1].startswith('+++ ')
    ]
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(lines)
        target = lines[start + 1][4:].split('\t')[0].strip()
        if target.startswith('b/'):
            target = target[2:]
        creates = lines[start][4:].strip().startswith('/dev/null')
        yield target, ''.join(lines[start:end]), creates


def apply(tree, diff_text, strict):
    command = ['patch', '-p1', '--forward', '--no-backup-if-mismatch', '-d', str(tree)]
    if strict:
        command.append('--fuzz=0')
    else:
        command.append('--ignore-whitespace')
    return subprocess.run(command, input=diff_text, text=True, encoding=ENCODING,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)


def fetch(version, path, cache_dir):
    cached = cache_dir / version / path
    if not cached.exists():
        cached.parent.mkdir(parents=True, exist_ok=True)
        url = SOURCE_URL.format(version=version, path=path)
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                cached.write_bytes(response.read())
        except urllib.error.HTTPError as exc:
            sys.exit('Could not download {} ({}). If the file moved upstream, the '
                     'patch needs updating.'.format(url, exc.code))
    return cached


def prepare_tree(tree, cache_dir, our_patches):
    """Builds a tree of the files our patches touch, with upstream changes applied."""
    version = (UPSTREAM_CORE / 'chromium_version.txt').read_text(encoding=ENCODING).strip()
    targets = set()
    for patch_path in our_patches:
        for target, _, creates in split_patch(patch_path.read_text(encoding=ENCODING)):
            if not creates:
                targets.add(target)

    if tree.exists():
        shutil.rmtree(tree)
    for target in sorted(targets):
        destination = tree / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(fetch(version, target, cache_dir), destination)

    ok = True
    for patches_dir in (UPSTREAM_CORE / 'patches', UPSTREAM_WINDOWS / 'patches'):
        for entry in read_series(patches_dir / 'series'):
            text = (patches_dir / entry).read_text(encoding=ENCODING)
            for target, diff_text, _ in split_patch(text):
                if target not in targets:
                    continue
                result = apply(tree, diff_text, strict=False)
                if result.returncode:
                    ok = False
                    print('UPSTREAM PATCH FAILED: {} on {}\n{}'.format(
                        entry, target, result.stdout))
    return version, sorted(targets), ok


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--work-dir', type=Path, default=ROOT / 'build' / 'check_patches',
                        help='Scratch directory. Default: %(default)s')
    parser.add_argument('--prepare-only', action='store_true',
                        help='Stop after creating the tree with upstream changes '
                        'applied (work-dir/tree); useful as a base for writing patches.')
    args = parser.parse_args()

    if not shutil.which('patch'):
        sys.exit('The `patch` program is required.')

    patches_dir = ROOT / 'patches'
    our_entries = read_series(patches_dir / 'series')
    our_patches = [patches_dir / entry for entry in our_entries]
    missing = [str(p) for p in our_patches if not p.is_file()]
    if missing:
        sys.exit('patches/series lists missing patches: {}'.format(', '.join(missing)))
    unlisted = sorted(
        str(p.relative_to(patches_dir)) for p in patches_dir.rglob('*.patch')
        if p not in our_patches)
    if unlisted:
        sys.exit('Patches not listed in patches/series: {}'.format(', '.join(unlisted)))

    tree = args.work_dir / 'tree'
    version, targets, ok = prepare_tree(tree, args.work_dir / 'cache', our_patches)
    print('Chromium {}: {} file(s) touched by {} Excalibur patch(es)'.format(
        version, len(targets), len(our_patches)))
    if args.prepare_only:
        print('Prepared', tree)
        sys.exit(0 if ok else 1)

    for entry, patch_path in zip(our_entries, our_patches):
        result = apply(tree, patch_path.read_text(encoding=ENCODING), strict=True)
        if result.returncode:
            ok = False
            print('FAILED  {}\n{}'.format(entry, result.stdout))
        else:
            print('ok      {}'.format(entry))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
