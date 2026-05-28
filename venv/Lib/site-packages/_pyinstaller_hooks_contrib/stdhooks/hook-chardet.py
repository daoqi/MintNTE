# ------------------------------------------------------------------
# Copyright (c) 2026 PyInstaller Development Team.
#
# This file is distributed under the terms of the GNU General Public
# License (version 2.0 or later).
#
# The full license is available in LICENSE, distributed with
# this software.
#
# SPDX-License-Identifier: GPL-2.0-or-later
# ------------------------------------------------------------------

from PyInstaller.utils.hooks import is_module_satisfies

hiddenimports = []
datas = []

# Starting with v7.0.0, we need to collect mypy extension, and the data files from chardet/models
if is_module_satisfies("chardet >= 7.0.0"):
    from PyInstaller.utils.hooks import collect_data_files
    from _pyinstaller_hooks_contrib.utils.mypy import find_mypyc_module_for_dist

    hiddenimports += find_mypyc_module_for_dist('chardet')
    datas += collect_data_files('chardet')

# In the Windows PyPI wheel of chardet v7.4.0post2, the extensions in `chardet.pipeline` seem to come with individual
# `__mypyc` counterparts (for example the `chardet.pipeline.orchestrator` extension references a corresponding
# `chardet.pipeline.orchestrator__mypyc` extension). Ensure all these are collected by collecting submodules.
if is_module_satisfies("chardet >= 7.4.0"):
    from PyInstaller.utils.hooks import collect_submodules
    hiddenimports += collect_submodules('chardet.pipeline')
