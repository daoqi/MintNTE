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

from PyInstaller.utils.hooks import collect_submodules, is_module_satisfies

# Starting with v14.3.0, we need to collect modules from `rich._unicode_data`.
if is_module_satisfies('rich >= 14.3.0'):
    hiddenimports = collect_submodules('rich._unicode_data')
