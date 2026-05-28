# ------------------------------------------------------------------
# Copyright (c) 2023 PyInstaller Development Team.
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

if is_module_satisfies("charset_normalizer >= 3.4.5"):
    from _pyinstaller_hooks_contrib.utils.mypy import find_mypyc_module_for_dist
    hiddenimports = find_mypyc_module_for_dist('charset_normalizer')
elif is_module_satisfies("charset_normalizer >= 3.0.1"):
    hiddenimports = ["charset_normalizer.md__mypyc"]
