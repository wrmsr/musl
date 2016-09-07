#! /usr/bin/env python

#   Copyright 2016 WebAssembly Community Group participants
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import glob
import itertools
import multiprocessing
import os
import shutil
import subprocess
import sys
import tempfile


verbose = False

# TODO add 'time'.
SRC_DIRS = [
    'ctype',
    'env',
    'errno',
    'exit',
    'internal',
    'ldso',
    'locale',
    'malloc',
    'math',
    'prng',
    'regex',
    'stdio',
    'stdlib',
    'string',
    'time',
    'unistd',
]

BLACKLIST = [
    # The JS version is nicer for now.
    'puts.c',  

    '_Exit.c',
    '__ctype_get_mb_cur_max.c',
    '__fdopen.c',
    '__fopen_rb_ca.c',
    '__libc_start_main.c',
    '__rem_pio2_large.c',
    '__stdio_write.c',
    '__stdout_write.c',
    '__tz.c',
    '__year_to_secs.c',
    'abort.c',
    # 'asprintf.c',
    'dlerror.c',
    # 'dprintf.c',
    'exit.c',
    # 'faccessat.c',
    # 'floatscan.c',
    # 'fprintf.c',
    # 'fscanf.c',
    # 'getcwd.c',
    # 'glob.c',
    # 'pclose.c',
    # 'pread.c',
    # 'printf.c',
    # 'pwrite.c',
    # 'qsort.c',
    # 'regcomp.c',
    # 'regexec.c',
    # 'scanf.c',
    # 'snprintf.c',
    # 'sprintf.c',
    # 'sscanf.c',
    # 'strftime.c',
    # 'strptime.c',
    # 'strsignal.c',
    # 'tcgetpgrp.c',
    'tcsetpgrp.c',
    'timer_create.c',
    # 'tmpfile.c',
    # 'utime.c',
    # 'vdprintf.c',
    # 'vfprintf.c',
    # 'vfscanf.c',
    # 'vsnprintf.c',
    # 'wcsftime.c',

    # Wide characters.
    # 'fgetwc.c',
    # 'fgetws.c',
    # 'fputwc.c',
    # 'fputws.c',
    # 'fwide.c',
    # 'fwprintf.c',
    # 'fwscanf.c',
    # 'fwscanf.c',
    # 'getw.c',
    # 'getwc.c',
    # 'getwchar.c',
    # 'iswalnum.c',
    # 'iswalpha.c',
    # 'iswblank.c',
    # 'iswcntrl.c',
    # 'iswctype.c',
    # 'iswdigit.c',
    # 'iswgraph.c',
    # 'iswlower.c',
    # 'iswprint.c',
    # 'iswpunct.c',
    # 'iswspace.c',
    # 'iswupper.c',
    # 'iswxdigit.c',
    # 'open_wmemstream.c',
    # 'putw.c',
    # 'putwc.c',
    # 'putwchar.c',
    # 'swprintf.c',
    # 'swscanf.c',
    # 'towctrans.c',
    # 'ungetwc.c',
    # 'vfwprintf.c',
    # 'vfwscanf.c',
    # 'vswprintf.c',
    # 'vswscanf.c',
    # 'vwprintf.c',
    # 'vwscanf.c',
    # 'wcpcpy.c',
    # 'wcpncpy.c',
    # 'wcscasecmp.c',
    # 'wcscasecmp_l.c',
    # 'wcscat.c',
    # 'wcschr.c',
    # 'wcscmp.c',
    # 'wcscpy.c',
    # 'wcscspn.c',
    # 'wcsdup.c',
    # 'wcslen.c',
    # 'wcsncasecmp.c',
    # 'wcsncasecmp_l.c',
    # 'wcsncat.c',
    # 'wcsncmp.c',
    # 'wcsncpy.c',
    # 'wcsnlen.c',
    # 'wcspbrk.c',
    # 'wcsrchr.c',
    # 'wcsspn.c',
    # 'wcsstr.c',
    # 'wcstok.c',
    # 'wcswcs.c',
    # 'wcswidth.c',
    # 'wctrans.c',
    # 'wcwidth.c',
    # 'wmemchr.c',
    # 'wmemcmp.c',
    # 'wmemcpy.c',
    # 'wmemmove.c',
    # 'wmemset.c',
    # 'wprintf.c',
    # 'wscanf.c',

    # stdio file lock.
    '__lockfile.c',
    'flockfile.c',
    'ftrylockfile.c',
    'funlockfile.c',
]

WARNINGS = [
    '-Wno-bitwise-op-parentheses',
    '-Wno-ignored-attributes',
    '-Wno-incompatible-library-redeclaration',
    '-Wno-pointer-sign',
    '-Wno-shift-op-parentheses',
    '-Wno-unknown-pragmas',
]


def check_output(cmd, **kwargs):
    cwd = kwargs.get('cwd', os.getcwd())
    if verbose:
        c = ' '.join('"' + c + '"' if ' ' in c else c for c in cmd)
        print '    `%s`, cwd=`%s`' % (c, cwd)
    return subprocess.check_output(cmd, cwd=cwd)


def change_extension(path, new_extension):
    return path[:path.rfind('.')] + new_extension


def create_version(musl):
    """musl's Makefile creates version.h"""
    script = os.path.join(musl, 'tools', 'version.sh')
    version = check_output(['sh', script], cwd=musl).strip()
    with open(os.path.join(musl, 'src', 'internal', 'version.h'), 'w') as v:
        v.write('#define VERSION "%s"\n' % version)


def build_alltypes(musl, arch):
    """Emulate musl's Makefile build of alltypes.h."""
    mkalltypes = os.path.join(musl, 'tools', 'mkalltypes.sed')
    inbits = os.path.join(musl, 'arch', arch, 'bits', 'alltypes.h.in')
    intypes = os.path.join(musl, 'include', 'alltypes.h.in')
    out = check_output(['sed', '-f', mkalltypes, inbits, intypes])
    with open(os.path.join(musl, 'arch', arch, 'bits', 'alltypes.h'), 'w') as o:
        o.write(out)


def musl_sources(musl_root):
    """musl sources to be built."""
    sources = []
    for d in SRC_DIRS:
        base = os.path.join(musl_root, 'src', d)
        pattern = os.path.join(base, '*.c')
        for f in glob.glob(pattern):
            if os.path.basename(f) in BLACKLIST:
                continue
            sources.append(os.path.join(base, f))
    return sorted(sources)


def includes(musl, arch):
    """Include path."""
    includes = [os.path.join(musl, 'include'),
                os.path.join(musl, 'src', 'internal'),
                os.path.join(musl, 'arch', arch)]
    return list(itertools.chain(*zip(['-I'] * len(includes), includes)))


class Compiler(object):
    """Compile source files."""

    def __init__(self, out, clang_dir, binaryen_dir, sexpr_wasm, musl, arch, tmpdir):
        self.out = out
        self.outbase = os.path.basename(self.out)
        self.clang_dir = clang_dir
        self.binaryen_dir = binaryen_dir
        self.sexpr_wasm = sexpr_wasm
        self.musl = musl
        self.arch = arch
        self.tmpdir = tmpdir
        self.compiled = []

    def __call__(self, src):
        target = '--target=wasm32-unknown-unknown'
        compile_cmd = [os.path.join(self.clang_dir, 'clang'), target, '-Os', '-emit-llvm', '-S', '-nostdinc']
        compile_cmd += includes(self.musl, self.arch)
        compile_cmd += WARNINGS
        check_output(compile_cmd + [src], cwd=self.tmpdir)
        return os.path.basename(src)[:-1] + 'll'    # .c -> .ll

    def compile(self, sources):
        if verbose:
            self.compiled = sorted([self(source) for source in sources])
        else:
            pool = multiprocessing.Pool()
            self.compiled = sorted(pool.map(self, sources))
            pool.close()
            pool.join()

    def link_assemble(self):
        bytecode = change_extension(self.out, '.bc')
        assembly = os.path.join(self.tmpdir, self.outbase + '.s')
        check_output([os.path.join(self.clang_dir, 'llvm-link'), '-o', bytecode] + self.compiled, cwd=self.tmpdir)
        check_output([os.path.join(self.clang_dir, 'llc'), bytecode, '-o', assembly], cwd=self.tmpdir)
        check_output([os.path.join(self.binaryen_dir, 's2wasm'), assembly, '--ignore-unknown', '-o', self.out], cwd=self.tmpdir)

    def binary(self):
        if self.sexpr_wasm:
            check_output([self.sexpr_wasm, self.out, '-o', change_extension(self.out, '.wasm')], cwd=self.tmpdir)


def run(clang_dir, binaryen_dir, sexpr_wasm, musl, arch, out, save_temps):
    if save_temps:
        tmpdir = os.path.join(os.getcwd(), 'libc_build')
        if os.path.isdir(tmpdir):
            shutil.rmtree(tmpdir)
        os.mkdir(tmpdir)
    else:
        tmpdir = tempfile.mkdtemp()

    try:
        create_version(musl)
        build_alltypes(musl, arch)
        sources = musl_sources(musl)
        compiler = Compiler(out, clang_dir, binaryen_dir, sexpr_wasm, musl, arch, tmpdir)
        compiler.compile(sources)
        compiler.link_assemble()
        compiler.binary()
    finally:
        if not save_temps:
            shutil.rmtree(tmpdir)


def getargs():
    import argparse
    parser = argparse.ArgumentParser(description='Build a hacky wasm libc.')
    default_bin_dir = os.path.join(os.getenv('HOME'), 'wasm-install', 'bin')
    parser.add_argument('--clang_dir', type=str, default=default_bin_dir, help='Clang binary directory')
    parser.add_argument('--binaryen_dir', type=str, default=default_bin_dir, help='binaryen binary directory')
    parser.add_argument('--sexpr_wasm', type=str, default=os.path.join(default_bin_dir, 'sexpr-wasm'), help='sexpr-wasm binary')
    parser.add_argument('--musl', type=str, default=os.getcwd(), help='musl libc root directory')
    parser.add_argument('--arch', type=str, default='wasm32', help='architecture to target')
    parser.add_argument('--out', '-o', type=str, default=os.path.join(os.getcwd(), 'musl.wast'), help='Output file')
    parser.add_argument('--save-temps', default=False, action='store_true', help='Save temporary files')
    parser.add_argument('--verbose', default=False, action='store_true', help='Verbose')
    return parser.parse_args()


if __name__ == '__main__':
    args = getargs()
    if args.verbose:
        verbose = True
    sys.exit(run(args.clang_dir, args.binaryen_dir, args.sexpr_wasm, args.musl, args.arch, args.out, args.save_temps))
