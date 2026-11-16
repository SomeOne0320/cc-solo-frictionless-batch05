import pytest

from frictionless import Dialect, FrictionlessException, system
from frictionless.resources import TableResource
from frictionless.schemes import MultipartControl

BASE = "data/multipart"

# General


def test_multipart_loader_header_aligned():
    with TableResource(
        path=f"{BASE}/orders1.csv",
        extrapaths=[f"{BASE}/orders2.csv"],
        control=MultipartControl(header_aligned=True),
    ) as resource:
        assert resource.header == ["region", "channel", "quantity"]
        assert resource.read_rows() == [
            {"region": "East", "channel": "online", "quantity": 10},
            {"region": "West, Central", "channel": 'say "hi"', "quantity": 20},
            {"region": "Multi\nLine", "channel": "store", "quantity": 30},
            {"region": "North", "channel": "online", "quantity": 40},
            {"region": "South", "channel": "store", "quantity": 50},
        ]


def test_multipart_loader_header_aligned_keeps_file_and_record_order():
    with TableResource(
        path=f"{BASE}/orders1.csv",
        extrapaths=[f"{BASE}/orders3.header-only.csv", f"{BASE}/orders2.csv"],
        control=MultipartControl(header_aligned=True),
    ) as resource:
        rows = resource.read_rows()
        assert [row["quantity"] for row in rows] == [10, 20, 30, 40, 50]
        assert [row["region"] for row in rows] == [
            "East",
            "West, Central",
            "Multi\nLine",
            "North",
            "South",
        ]


def test_multipart_loader_header_aligned_header_only_file():
    # The first file's header is the canonical one even if it has no data rows
    with TableResource(
        path=f"{BASE}/orders3.header-only.csv",
        extrapaths=[f"{BASE}/orders1.csv"],
        control=MultipartControl(header_aligned=True),
    ) as resource:
        assert resource.header == ["quantity", "region", "channel"]
        assert resource.read_rows() == [
            {"quantity": 10, "region": "East", "channel": "online"},
            {"quantity": 20, "region": "West, Central", "channel": 'say "hi"'},
            {"quantity": 30, "region": "Multi\nLine", "channel": "store"},
        ]


def test_multipart_loader_header_aligned_empty_file():
    with TableResource(
        path=f"{BASE}/orders1.csv",
        extrapaths=[f"{BASE}/orders8.empty.csv", f"{BASE}/orders2.csv"],
        control=MultipartControl(header_aligned=True),
    ) as resource:
        assert len(resource.read_rows()) == 5


def test_multipart_loader_header_aligned_empty_first_file():
    with TableResource(
        path=f"{BASE}/orders8.empty.csv",
        extrapaths=[f"{BASE}/orders1.csv"],
        control=MultipartControl(header_aligned=True),
    ) as resource:
        assert resource.header == ["region", "channel", "quantity"]
        assert len(resource.read_rows()) == 3


def test_multipart_loader_header_aligned_descriptor():
    with TableResource.from_descriptor(
        {
            "name": "name",
            "path": f"{BASE}/orders1.csv",
            "extrapaths": [f"{BASE}/orders2.csv"],
            "dialect": {"multipart": {"headerAligned": True}},
        }
    ) as resource:
        assert resource.header == ["region", "channel", "quantity"]
        assert len(resource.read_rows()) == 5


def test_multipart_loader_header_aligned_infer():
    resource = TableResource(
        path=f"{BASE}/orders1.csv",
        extrapaths=[f"{BASE}/orders2.csv"],
        control=MultipartControl(header_aligned=True),
    )
    resource.infer()
    assert resource.schema.field_names == ["region", "channel", "quantity"]
    assert resource.header == ["region", "channel", "quantity"]


def test_multipart_loader_header_aligned_validate():
    resource = TableResource(
        path=f"{BASE}/orders1.csv",
        extrapaths=[f"{BASE}/orders2.csv"],
        control=MultipartControl(header_aligned=True),
    )
    report = resource.validate()
    assert report.valid
    assert report.task.stats.get("rows") == 5


# Errors


def test_multipart_loader_header_aligned_missing_column_error():
    resource = TableResource(
        path=f"{BASE}/orders1.csv",
        extrapaths=[f"{BASE}/orders4.missing-column.csv"],
        control=MultipartControl(header_aligned=True),
    )
    with pytest.raises(FrictionlessException) as excinfo:
        resource.read_rows()
    error = excinfo.value.error
    assert error.type == "source-error"
    assert "orders4.missing-column.csv" in error.note
    assert 'missing column(s): "channel"' in error.note


def test_multipart_loader_header_aligned_extra_column_error():
    resource = TableResource(
        path=f"{BASE}/orders1.csv",
        extrapaths=[f"{BASE}/orders5.extra-column.csv"],
        control=MultipartControl(header_aligned=True),
    )
    with pytest.raises(FrictionlessException) as excinfo:
        resource.read_rows()
    error = excinfo.value.error
    assert error.type == "source-error"
    assert "orders5.extra-column.csv" in error.note
    assert 'extra column(s): "note"' in error.note


def test_multipart_loader_header_aligned_duplicate_label_error():
    resource = TableResource(
        path=f"{BASE}/orders1.csv",
        extrapaths=[f"{BASE}/orders6.duplicate-label.csv"],
        control=MultipartControl(header_aligned=True),
    )
    with pytest.raises(FrictionlessException) as excinfo:
        resource.read_rows()
    error = excinfo.value.error
    assert error.type == "source-error"
    assert "orders6.duplicate-label.csv" in error.note
    assert 'duplicate column name(s) in the header: "channel"' in error.note


def test_multipart_loader_header_aligned_blank_label_error():
    resource = TableResource(
        path=f"{BASE}/orders1.csv",
        extrapaths=[f"{BASE}/orders7.blank-label.csv"],
        control=MultipartControl(header_aligned=True),
    )
    with pytest.raises(FrictionlessException) as excinfo:
        resource.read_rows()
    error = excinfo.value.error
    assert error.type == "source-error"
    assert "orders7.blank-label.csv" in error.note
    assert "blank column name(s) in the header at position(s): 2" in error.note


def test_multipart_loader_header_aligned_first_file_duplicate_label_error():
    resource = TableResource(
        path=f"{BASE}/orders6.duplicate-label.csv",
        extrapaths=[f"{BASE}/orders1.csv"],
        control=MultipartControl(header_aligned=True),
    )
    with pytest.raises(FrictionlessException) as excinfo:
        resource.read_rows()
    error = excinfo.value.error
    assert error.type == "source-error"
    assert "orders6.duplicate-label.csv" in error.note
    assert "duplicate column name(s)" in error.note


def test_multipart_loader_header_aligned_validate_missing_column_error():
    resource = TableResource(
        path=f"{BASE}/orders1.csv",
        extrapaths=[f"{BASE}/orders4.missing-column.csv"],
        control=MultipartControl(header_aligned=True),
    )
    report = resource.validate()
    assert not report.valid
    assert report.flatten(["type", "note"]) == [
        [
            "source-error",
            f'file "{BASE}/orders4.missing-column.csv" has a header that does not '
            f'match the header of file "{BASE}/orders1.csv": '
            'missing column(s): "channel"',
        ]
    ]


def test_multipart_loader_header_aligned_not_csv_error():
    resource = TableResource(
        path=f"{BASE}/orders1.csv",
        extrapaths=[f"{BASE}/orders2.csv"],
        format="json",
        control=MultipartControl(header_aligned=True),
    )
    with pytest.raises(FrictionlessException) as excinfo:
        resource.read_rows()
    error = excinfo.value.error
    assert error.type == "source-error"
    assert "only supported for CSV files" in error.note


def test_multipart_loader_header_aligned_header_disabled_error():
    dialect = Dialect(header=False)
    dialect.add_control(MultipartControl(header_aligned=True))
    resource = TableResource(
        path=f"{BASE}/orders1.csv",
        extrapaths=[f"{BASE}/orders2.csv"],
        dialect=dialect,
    )
    with pytest.raises(FrictionlessException) as excinfo:
        resource.read_rows()
    error = excinfo.value.error
    assert error.type == "source-error"
    assert 'requires the "header" dialect option' in error.note


def test_multipart_loader_header_aligned_multiple_header_rows_error():
    dialect = Dialect(header_rows=[1, 2])
    dialect.add_control(MultipartControl(header_aligned=True))
    resource = TableResource(
        path=f"{BASE}/orders1.csv",
        extrapaths=[f"{BASE}/orders2.csv"],
        dialect=dialect,
    )
    with pytest.raises(FrictionlessException) as excinfo:
        resource.read_rows()
    error = excinfo.value.error
    assert error.type == "source-error"
    assert "requires a single header row" in error.note


# Default (positional) mode is not affected


def test_multipart_loader_header_aligned_default_off():
    with TableResource(
        path=f"{BASE}/orders1.csv",
        extrapaths=[f"{BASE}/orders2.csv"],
    ) as resource:
        assert resource.header == ["region", "channel", "quantity"]
        # Without the option the files are concatenated positionally
        # so the reordered columns of the second file are misplaced
        assert resource.read_rows() == [
            {"region": "East", "channel": "online", "quantity": 10},
            {"region": "West, Central", "channel": 'say "hi"', "quantity": 20},
            {"region": "Multi\nLine", "channel": "store", "quantity": 30},
            {"region": "online", "channel": "North", "quantity": 40},
            {"region": "store", "channel": "South", "quantity": 50},
        ]


# Streaming


def test_multipart_loader_header_aligned_is_streaming(tmpdir):
    # The first file is bigger than the detector buffer so reading
    # the first rows doesn't require opening the following files
    path1 = str(tmpdir.join("big1.csv"))
    path2 = str(tmpdir.join("missing.csv"))
    with open(path1, "w") as file:
        file.write("a,b\n")
        for number in range(20000):
            file.write(f"{number},x{number}\n")
    control = MultipartControl(header_aligned=True)
    with TableResource(
        path=path1, extrapaths=[path2], control=control
    ) as resource:
        row = next(resource.row_stream)
        assert row.to_dict() == {"a": 0, "b": "x0"}


def test_multipart_loader_header_aligned_late_error(tmpdir):
    # The header error of the second file is beyond the detector
    # sample so it's raised while reading the rows
    path1 = str(tmpdir.join("big1.csv"))
    path2 = str(tmpdir.join("bad2.csv"))
    with open(path1, "w") as file:
        file.write("a,b\n")
        for number in range(500):
            file.write(f"{number},x{number}\n")
    with open(path2, "w") as file:
        file.write("a,c\n1,2\n")
    control = MultipartControl(header_aligned=True)
    resource = TableResource(path=path1, extrapaths=[path2], control=control)
    with system.use_context(trusted=True):
        report = resource.validate()
    assert not report.valid
    assert report.flatten(["type", "note"]) == [
        [
            "source-error",
            f'file "{path2}" has a header that does not match the header '
            f'of file "{path1}": missing column(s): "b"; extra column(s): "c"',
        ]
    ]
