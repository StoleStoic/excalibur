#!/usr/bin/env python3
# Copyright (c) 2026 The Excalibur Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""
Excalibur build script.

Excalibur is an overlay on ungoogled-chromium-windows (the git submodule in
upstream/). This script:

  1. Stages a merged copy of the upstream build tree with Excalibur's patches
     appended to the patch series and Excalibur's GN flags merged in.
  2. Runs the upstream build.py inside that staged tree (Windows only).
  3. Optionally packages the result into dist/ under Excalibur's name.

Staging is platform independent, so `build.py --stage-only` works anywhere and
is what CI uses.
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UPSTREAM = ROOT / 'upstream' / 'ungoogled-chromium-windows'
ENCODING = 'UTF-8'
NAME = 'excalibur'

# Never touched when re-staging: holds the 100 GB source tree and build output.
_PRESERVED = {'build'}
_FLAG_RE = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=')


def read_series(path):
    """Returns the patch paths listed in a quilt-style series file."""
    entries = []
    for line in path.read_text(encoding=ENCODING).splitlines():
        line = line.split(' #')[0].strip()
        if line and not line.startswith('#'):
            entries.append(line)
    return entries


def parse_flags(text):
    """Returns {name: full line} for every GN assignment in text."""
    flags = {}
    for line in text.splitlines():
        match = _FLAG_RE.match(line)
        if match:
            flags[match.group(1)] = line.strip()
    return flags


def merge_flags(stage_dir):
    """
    Merges flags.excalibur.gn into the staged upstream flag files.

    A flag upstream already sets is replaced in place (GN rejects duplicate
    assignments in args.gn); new flags are appended to flags.windows.gn.
    """
    ours = parse_flags((ROOT / 'flags.excalibur.gn').read_text(encoding=ENCODING))
    remaining = dict(ours)
    for flag_file in (stage_dir / 'ungoogled-chromium' / 'flags.gn',
                      stage_dir / 'flags.windows.gn'):
        lines = flag_file.read_text(encoding=ENCODING).splitlines()
        for i, line in enumerate(lines):
            match = _FLAG_RE.match(line)
            if match and match.group(1) in ours:
                lines[i] = ours[match.group(1)]
                remaining.pop(match.group(1), None)
        flag_file.write_text('\n'.join(lines) + '\n', encoding=ENCODING)
    if remaining:
        windows_flags = stage_dir / 'flags.windows.gn'
        with windows_flags.open('a', encoding=ENCODING) as out:
            out.write('\n'.join(remaining.values()) + '\n')
    return ours


def stage(stage_dir):
    """Creates/refreshes the merged build tree in stage_dir."""
    if not (UPSTREAM / 'build.py').exists():
        sys.exit('Upstream submodule is missing. Run:\n'
                 '  git submodule update --init --recursive')
    stage_dir.mkdir(parents=True, exist_ok=True)
    for child in stage_dir.iterdir():
        if child.name in _PRESERVED or child == ROOT or child in ROOT.parents:
            continue  # Keep build output, and this repo if it lives inside stage_dir.
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()
    shutil.copytree(UPSTREAM, stage_dir, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('.git', 'build'))

    # Append our patches after upstream's Windows patches.
    entries = read_series(ROOT / 'patches' / 'series')
    for entry in entries:
        source = ROOT / 'patches' / entry
        if not source.is_file():
            sys.exit('patches/series lists a missing patch: {}'.format(entry))
        target = stage_dir / 'patches' / entry
        if target.exists():
            sys.exit('Patch path collides with an upstream patch: {}'.format(entry))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    with (stage_dir / 'patches' / 'series').open('a', encoding=ENCODING) as series:
        series.write('\n' + '\n'.join(entries) + '\n')

    flags = merge_flags(stage_dir)
    print('Staged {} with {} Excalibur patch(es) and {} flag override(s)'.format(
        stage_dir, len(entries), len(flags)))


def package(stage_dir, cpu_arch):
    """Runs upstream packaging and collects renamed outputs into dist/."""
    subprocess.run([sys.executable, 'package.py', '--cpu-arch', cpu_arch],
                   cwd=stage_dir, check=True)
    collect(stage_dir / 'build', ROOT / 'dist')


def collect(source_dir, dist_dir):
    """Copies upstream-named packages from source_dir to dist_dir, renamed."""
    dist_dir.mkdir(parents=True, exist_ok=True)
    found = sorted(p for p in source_dir.glob('ungoogled-chromium_*') if p.is_file())
    if not found:
        sys.exit('No packages found in {}'.format(source_dir))
    for path in found:
        target = dist_dir / path.name.replace('ungoogled-chromium_', NAME + '_', 1)
        shutil.copyfile(path, target)
        print('Packaged', target)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--stage-dir', type=Path, default=ROOT / 'build' / 'stage',
                        help='Where to create the merged build tree. Keep it short on '
                        'Windows (e.g. C:\\ex) to stay under path length limits. '
                        'Default: %(default)s')
    parser.add_argument('--stage-only', action='store_true',
                        help='Only create the merged tree; do not build.')
    parser.add_argument('--package', action='store_true',
                        help='After building, create the installer and zip in dist/.')
    parser.add_argument('--collect', type=Path, metavar='DIR',
                        help='Only rename already-built packages from DIR into dist/.')
    parser.add_argument('--x86', action='store_true', help='Build 32-bit x86.')
    parser.add_argument('--arm', action='store_true', help='Build ARM64.')
    parser.add_argument('-j', type=int, dest='thread_count',
                        help='Number of CPU threads to use for compiling.')
    args, upstream_args = parser.parse_known_args()

    if args.collect:
        collect(args.collect, ROOT / 'dist')
        return

    stage_dir = args.stage_dir.resolve()
    stage(stage_dir)
    if args.stage_only:
        return

    if sys.platform != 'win32':
        sys.exit('Building requires Windows. Use --stage-only on other platforms.')

    command = [sys.executable, 'build.py'] + upstream_args
    if args.x86:
        command.append('--x86')
    if args.arm:
        command.append('--arm')
    if args.thread_count:
        command += ['-j', str(args.thread_count)]
    subprocess.run(command, cwd=stage_dir, check=True)

    if args.package:
        package(stage_dir, '32bit' if args.x86 else 'arm' if args.arm else '64bit')


if __name__ == '__main__':
    main()
