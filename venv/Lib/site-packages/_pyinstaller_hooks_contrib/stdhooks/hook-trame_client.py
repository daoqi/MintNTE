# ------------------------------------------------------------------
# Copyright (c) 2024 PyInstaller Development Team.
#
# This file is distributed under the terms of the GNU General Public
# License (version 2.0 or later).
#
# The full license is available in LICENSE, distributed with
# this software.
#
# SPDX-License-Identifier: GPL-2.0-or-later
# ------------------------------------------------------------------

from PyInstaller.utils.hooks import collect_data_files, copy_metadata, is_module_satisfies

datas = collect_data_files("trame_client", subdir="module")

# Starting with trame-client v3.12.0, version information (obtained from metadata) is required.
if is_module_satisfies("trame-client >= 3.12.0"):
    datas += copy_metadata("trame-client")
