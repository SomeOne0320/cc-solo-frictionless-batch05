---
script:
  basepath: data
---

# Multipart Scheme

You can read and write files split into chunks with Frictionless.

## Reading Data

You can read using `Package/Resource`, for example:

```python script tabs=Python
from pprint import pprint
from frictionless import Resource

resource = Resource(path='chunk1.csv', extrapaths=['chunk2.csv'])
pprint(resource.read_rows())
```

## Header-Aligned Concatenation

By default the files are concatenated positionally: the header row of every file after the first one is skipped and the columns are matched by their positions. If the files have the same columns but in a different order, you can align them by their header names instead:

```python script tabs=Python
from pprint import pprint
from frictionless import Resource
from frictionless.schemes import MultipartControl

control = MultipartControl(header_aligned=True)
resource = Resource(
    path='multipart/orders1.csv',
    extrapaths=['multipart/orders2.csv'],
    control=control,
)
pprint(resource.read_rows())
```

With this option enabled:

- the header of the first file is used as the canonical one
- every other file must have a header with the same set of column names (matched exactly); its records are reordered to the canonical positions while reading
- a file having only a header row is allowed and doesn't produce data rows
- a file with a blank or duplicated column name, or with missing/extra columns compared to the first file, raises an error before its data is read

Currently it's supported for local, uncompressed and UTF-8 encoded CSV files having a single header row and sharing the same CSV dialect. The option is disabled by default.

## Writing Data

A similiar approach can be used for writing:

```python tabs=Python
from frictionless import Resource

resource = Resource(path='table.json')
resource.write('table{number}.json', scheme="multipart", control={"chunkSize": 1000000})
```

## Configuration

There is a `Control` to configure how Frictionless reads files using this scheme. For example:

```python tabs=Python
from frictionless import Resource
from frictionless.plugins.multipart import MultipartControl

control = MultipartControl(chunk_size=1000000)
resource = Resource(data=[['id', 'name'], [1, 'english'], [2, 'german']])
resource.write('table{number}.json', scheme="multipart", control=control)
```

## Reference

```yaml reference
references:
  - frictionless.schemes.MultipartControl
```
