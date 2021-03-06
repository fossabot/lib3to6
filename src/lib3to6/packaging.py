# This file is part of the lib3to6 project
# https://github.com/mbarkhau/lib3to6
#
# (C) 2018 Manuel Barkhau (@mbarkhau)
# SPDX-License-Identifier: MIT

import os
import sys
import shutil
import tempfile
import typing as typ
import hashlib as hl
import pathlib2 as pl

from . import transpile
from . import common


ENV_PATH = str(pl.Path(sys.executable).parent.parent)


PYTHON_TAG_PREFIXES = {
    "py": "Generic Python",
    "cp": "CPython",
    "ip": "IronPython",
    "pp": "PyPy",
    "jy": "Jython",
}


CACHE_DIR = pl.Path(tempfile.gettempdir()) / ".lib3to6_cache"


def eval_build_config() -> common.BuildConfig:
    # TODO (mb 2018-06-07): Get options from setup.cfg
    # python_tags = "py2.py3"
    # for argi, arg in enumerate(sys.argv):
    #     if "--python-tag" in arg:
    #         if "=" in arg:
    #             python_tags = arg.split("=", 1)[-1]
    #         else:
    #             python_tags = sys.argv[argi + 1]

    return {
        "target_version"  : "2.7",
        "force_transpile" : "1",
        "fixers"          : "",
        "checkers"        : "",
    }


def _ingore_tmp_files(src: str, names: typ.List[str]) -> typ.List[str]:
    if src.endswith("build"):
        return names
    if src.endswith("dist"):
        return names
    if src.endswith("__pycache__"):
        return names
    return [name for name in names if name.endswith(".pyc")]


def init_build_package_dir(local_package_dir: common.PackageDir) -> common.PackageDir:
    output_dir = pl.Path("build") / "lib3to6_out"
    try:
        output_dir.mkdir(parents=True)
    except Exception:
        # forgiveness > permission
        pass

    build_package_dir: common.PackageDir = {}

    for package, src_package_dir in local_package_dir.items():
        # TODO (mb 2018-08-25): Make sure src_package_dir is a
        #   relative path.
        is_abs_path = pl.Path(src_package_dir) == pl.Path(src_package_dir).absolute()
        if is_abs_path:
            raise Exception(f"package_dir must use relative paths, got '{src_package_dir}'")

        build_package_subdir = output_dir / src_package_dir

        # TODO (mb 2018-08-25): As an optimization, we could
        #   restrict deletion to files that we manipulate, in
        #   other words, to *.py files.
        if build_package_subdir.exists():
            shutil.rmtree(build_package_subdir)

        shutil.copytree(
            src_package_dir,
            str(build_package_subdir),
            ignore=_ingore_tmp_files,
        )

        build_package_dir[package] = str(build_package_subdir)

    return build_package_dir


def build_package(cfg: common.BuildConfig, package: str, build_dir: str) -> None:
    for root, dirs, files in os.walk(build_dir):
        for filename in files:
            filepath = pl.Path(root) / filename
            if filepath.suffix != ".py":
                continue

            with open(filepath, mode="rb") as fh:
                module_source_data = fh.read()

            filehash = hl.sha1(module_source_data).hexdigest()
            cache_path = CACHE_DIR / (filehash + ".py")

            if int(cfg["force_transpile"]) or not cache_path.exists():
                fixed_module_source_data = transpile.transpile_module_data(cfg, module_source_data)
                with open(cache_path, mode="wb") as fh:
                    fh.write(fixed_module_source_data)

            shutil.copy(cache_path, filepath)


def build_packages(cfg: common.BuildConfig, build_package_dir: common.PackageDir) -> None:
    CACHE_DIR.mkdir(exist_ok=True)

    for package, build_dir in build_package_dir.items():
        build_package(cfg, package, build_dir)


def fix(package_dir: common.PackageDir=None) -> common.PackageDir:
    if package_dir is None:
        package_dir = {"": "."}

    build_package_dir = init_build_package_dir(package_dir)
    build_cfg = eval_build_config()
    build_packages(build_cfg, build_package_dir)
    return build_package_dir
