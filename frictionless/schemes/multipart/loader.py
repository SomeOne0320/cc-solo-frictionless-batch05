from __future__ import annotations

import csv
import io
import tempfile
from itertools import chain
from typing import TYPE_CHECKING, Any, Iterator, List, Optional

from ... import errors, helpers, types
from ...exception import FrictionlessException
from ...platform import platform
from ...resources import FileResource
from ...system import Loader
from .control import MultipartControl

if TYPE_CHECKING:
    from ...resource import Resource

# NOTE:
# Currently the situation with header/no-header concatenation is complicated
# We need to review it and add more tests for general/tabular edge cases


class MultipartLoader(Loader):
    """Multipart loader implementation."""

    # Read

    def read_byte_stream_create(self):  # type: ignore
        assert self.resource.normpath
        remote = self.resource.remote
        control = MultipartControl.from_dialect(self.resource.dialect)
        if control.header_aligned:
            self.ensure_header_aligned()
            return MultipartHeaderAlignedByteStream(
                self.resource.normpaths,
                remote=remote,
                resource=self.resource,
            )
        headless = self.resource.dialect.header is False
        headless = headless or self.resource.format != "csv"
        return MultipartByteStream(
            self.resource.normpaths,
            remote=remote,
            headless=headless,
        )

    def ensure_header_aligned(self):
        if self.resource.format != "csv":
            note = "header-aligned multipart reading is only supported for CSV files"
            raise FrictionlessException(errors.SourceError(note=note))
        if not self.resource.dialect.header:
            note = (
                'header-aligned multipart reading requires the "header" '
                "dialect option to be enabled"
            )
            raise FrictionlessException(errors.SourceError(note=note))
        if self.resource.dialect.header_rows != [1]:
            note = "header-aligned multipart reading requires a single header row"
            raise FrictionlessException(errors.SourceError(note=note))

    # Write

    def write_byte_stream_save(self, byte_stream: types.IByteStream):
        assert self.resource.normpath
        control = MultipartControl.from_dialect(self.resource.dialect)
        number = 0
        while True:
            bytes = byte_stream.read(control.chunk_size)
            if not bytes:
                break
            number += 1
            path = self.resource.normpath.format(number=number)
            with tempfile.NamedTemporaryFile(delete=False) as file:
                file.write(bytes)
            helpers.move_file(file.name, path)


# Internal


class MultipartByteStream:
    def __init__(self, paths: List[str], *, remote: bool, headless: bool):
        self.__paths = paths
        self.__remote = remote
        self.__headless = headless
        self.__line_stream = self.read_line_stream()

    def __enter__(self):
        return self

    def __exit__(self, *args: Any, **kwargs: Any):
        pass

    @property
    def remote(self):
        return self.__remote

    @property
    def closed(self):
        return False

    def readable(self):
        return True

    def seekable(self):
        return True

    def writable(self):
        return False

    def close(self):
        pass

    def flush(self):
        pass

    def read1(self, size: int):
        return self.read(size)

    def seek(self, offset: int):
        assert offset == 0
        self.__line_stream = self.read_line_stream()

    def read(self, size: int):
        res = b""
        while True:
            try:
                res += next(self.__line_stream)
            except StopIteration:
                break
            if len(res) > size:
                break
        return res

    def read_line_stream(self):
        for number, path in enumerate(self.__paths, start=1):
            with FileResource(path=path) as resource:
                for line_number, line in enumerate(resource.byte_stream, start=1):
                    if not self.__headless and number > 1 and line_number == 1:
                        continue
                    yield line


class MultipartHeaderAlignedByteStream:
    """Byte stream concatenating CSV files aligning columns by header names.

    The header of the first non-empty file is used as the canonical one. Every
    other file must have a header with the same set of column names (matched
    exactly) and its records are reordered to the canonical positions while
    reading. The files are processed one by one so the reading stays streaming
    and there is no need to load all the files into memory.
    """

    def __init__(self, paths: List[str], *, remote: bool, resource: Resource):
        self.__paths = paths
        self.__remote = remote
        self.__resource = resource
        self.__line_stream = self.read_line_stream()

    def __enter__(self):
        return self

    def __exit__(self, *args: Any, **kwargs: Any):
        pass

    @property
    def remote(self):
        return self.__remote

    @property
    def closed(self):
        return False

    def readable(self):
        return True

    def seekable(self):
        return True

    def writable(self):
        return False

    def close(self):
        self.__line_stream.close()

    def flush(self):
        pass

    def read1(self, size: int):
        return self.read(size)

    def seek(self, offset: int):
        assert offset == 0
        self.__line_stream.close()
        self.__line_stream = self.read_line_stream()

    def read(self, size: int):
        res = b""
        while True:
            try:
                res += next(self.__line_stream)
            except StopIteration:
                break
            if len(res) > size:
                break
        return res

    def read_line_stream(self) -> Iterator[bytes]:
        resource = self.__resource
        control = platform.frictionless_formats.CsvControl.from_dialect(
            resource.dialect
        )
        defined_encoding = resource.get_defined("encoding")
        emit_encoding = defined_encoding or "utf-8"
        canonical: Optional[List[str]] = None
        canonical_path: Optional[str] = None
        config: Any = None
        writer_buffer = io.StringIO()
        writer: Any = None
        for path in self.__paths:
            with FileResource(path=path) as part:
                part_encoding = defined_encoding or part.encoding or "utf-8"
                text_stream = io.TextIOWrapper(
                    part.byte_stream, part_encoding, newline=""
                )
                if config is None:
                    # The CSV dialect is detected once from the first non-empty
                    # file as all the files share the same dialect
                    sample = extract_sample(text_stream)
                    if not sample:
                        continue
                    config = detect_csv_config(control, sample)
                    writer = csv.writer(writer_buffer, dialect=config)
                    source = chain(sample, text_stream)
                else:
                    source = text_stream
                reader = csv.reader(source, dialect=config)
                header = next(reader, None)
                if header is None:
                    continue
                ensure_header_is_valid(header, path=path)
                if canonical is None:
                    canonical = header
                    canonical_path = path
                    permutation = list(range(len(canonical)))
                    yield serialize_record(
                        writer, writer_buffer, canonical, emit_encoding
                    )
                else:
                    ensure_header_matches(
                        header, canonical, path=path, canonical_path=canonical_path
                    )
                    permutation = [header.index(name) for name in canonical]
                for record in reader:
                    if not record:
                        # A blank line is emitted as-is to keep the blank row
                        # handling of the CSV parser intact
                        aligned = record
                    else:
                        aligned = [
                            record[index] if index < len(record) else ""
                            for index in permutation
                        ]
                        if len(record) > len(header):
                            aligned.extend(record[len(header):])
                    yield serialize_record(
                        writer, writer_buffer, aligned, emit_encoding
                    )


SAMPLE_SIZE = 100


def serialize_record(
    writer: Any, buffer: io.StringIO, record: List[str], encoding: str
) -> bytes:
    buffer.seek(0)
    buffer.truncate(0)
    writer.writerow(record)
    return buffer.getvalue().encode(encoding)


def extract_sample(text_stream: types.ITextStream) -> List[str]:
    sample: List[str] = []
    while True:
        try:
            sample.append(next(text_stream))
        except StopIteration:
            break
        if len(sample) >= SAMPLE_SIZE:
            break
    return sample


# NOTE:
# The detection logic mirrors the CSV parser one so the header-aligned
# stream is parsed with the same dialect as a positionally concatenated one


def detect_csv_config(control: Any, sample: List[str]) -> Any:
    delimiter = control.get_defined("delimiter", default=",\t;|")
    try:
        config = csv.Sniffer().sniff("".join(sample), delimiter)  # type: ignore
    except csv.Error:
        config = csv.excel()
    # We can't rely on this guess as it's can be confused with embedded JSON
    # https://github.com/frictionlessdata/frictionless-py/issues/493
    if config.quotechar == "'":
        config.quotechar = '"'
    control.set_not_defined("delimiter", config.delimiter, distinct=True)
    control.set_not_defined("line_terminator", config.lineterminator, distinct=True)
    control.set_not_defined("escape_char", config.escapechar, distinct=True)
    control.set_not_defined("quote_char", config.quotechar, distinct=True)
    control.set_not_defined("skip_initial_space", config.skipinitialspace, distinct=True)
    return control.to_python()


def ensure_header_is_valid(header: List[str], *, path: str):
    if not header:
        note = f'file "{path}" has a blank header'
        raise FrictionlessException(errors.SourceError(note=note))
    blank = [
        str(position)
        for position, name in enumerate(header, start=1)
        if not name.strip()
    ]
    if blank:
        note = (
            f'file "{path}" has blank column name(s) in the header '
            f'at position(s): {", ".join(blank)}'
        )
        raise FrictionlessException(errors.SourceError(note=note))
    duplicates = []
    for name in header:
        if header.count(name) > 1 and name not in duplicates:
            duplicates.append(name)
    if duplicates:
        names = ", ".join(f'"{name}"' for name in duplicates)
        note = f'file "{path}" has duplicate column name(s) in the header: {names}'
        raise FrictionlessException(errors.SourceError(note=note))


def ensure_header_matches(
    header: List[str],
    canonical: List[str],
    *,
    path: str,
    canonical_path: Optional[str],
):
    missing = [name for name in canonical if name not in header]
    extra = [name for name in header if name not in canonical]
    if missing or extra:
        problems = []
        if missing:
            names = ", ".join(f'"{name}"' for name in missing)
            problems.append(f"missing column(s): {names}")
        if extra:
            names = ", ".join(f'"{name}"' for name in extra)
            problems.append(f"extra column(s): {names}")
        note = (
            f'file "{path}" has a header that does not match the header '
            f'of file "{canonical_path}": {"; ".join(problems)}'
        )
        raise FrictionlessException(errors.SourceError(note=note))
