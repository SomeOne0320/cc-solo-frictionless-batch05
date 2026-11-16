from __future__ import annotations

import attrs

from ...dialect import Control
from . import settings


@attrs.define(kw_only=True, repr=False)
class MultipartControl(Control):
    """Multipart control representation"""

    type = "multipart"

    chunk_size: int = settings.DEFAULT_CHUNK_SIZE
    """
    Specifies chunk size for the multipart file.
    """

    header_aligned: bool = settings.DEFAULT_HEADER_ALIGNED
    """
    Align the files by their header names when concatenating instead of
    concatenating them positionally. The first file's header is used as
    the canonical one and every other file must have the same set of column
    names (matched exactly) which are reordered to their canonical positions
    while reading. Currently it's only supported for local, uncompressed and
    UTF-8 encoded CSV files having a single header row and sharing the same
    CSV dialect. Default is False.
    """

    # Metadata

    metadata_profile_patch = {
        "properties": {
            "chunkSize": {"type": "integer"},
            "headerAligned": {"type": "boolean"},
        },
    }
