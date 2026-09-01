---
title: Online Sheets
description: Create, read, and update WeCom online sheets across supported CLI generations.
---

# Online Sheets

`online.sheets` translates standard-sheet operations across legacy CLI `0.1.x` and current CLI `1.1+`. Structure and cell-range reads are read-only; creation, deletion, row append, and range update operations require explicit confirmation.

## Create and inspect a sheet

```python
from online.sheets import create_sheet, get_info

created = create_sheet("Weekly Metrics", confirmed=True)
info = get_info(docid="DOC_ID")
```

Legacy `create_sheet()` uses document type `4`; current releases use `sheet create`. `get_info()` reads sheet metadata and subsheet structure.

## Read a cell range

```python
from online.sheets import get_range

data = get_range(
    docid="DOC_ID",
    sheet_id="SHEET_ID",
    cell_range="A1:D100",
)
```

This requires CLI `1.1+` and calls `sheet ranges get`. Use `mode="csv"` for a CSV response; `cell_range` is required in the default structured mode.

## Add and remove a subsheet

```python
from online.sheets import add_subsheet, delete_subsheet

added = add_subsheet(
    docid="DOC_ID",
    title="Week 28",
    row_count=100,
    column_count=12,
    index=0,
    confirmed=True,
)

deleted = delete_subsheet(
    docid="DOC_ID",
    sheet_id="SHEET_ID",
    confirmed=True,
)
```

Deletion is irreversible from the wrapper's point of view. Verify the sheet ID and target document immediately before the call.

## Append a row

Primitive Python values are converted into WeCom cell payloads:

```python
from online.sheets import append_row

append_row(
    docid="DOC_ID",
    sheet_id="SHEET_ID",
    values=["Completed", 42, None],
    confirmed=True,
)
```

Numbers become `NUMBER` cells. Other primitive values become `TEXT` cells; `None` becomes an empty string.

## Use typed cells

```python
values = [
    {"type": "text", "text": "Issue"},
    {"type": "number", "number": 17},
    {"type": "formula", "formula": "=SUM(B2:B8)"},
    {
        "type": "link",
        "text": "Repository",
        "url": "https://github.com/tzwkb/wecom-agent",
    },
]
```

Already encoded dictionaries containing `data_type`, `cell_value`, or `cell_format` are preserved. Formula enums are normalized to legacy `FORMUAL` or current `FORMULA` as required by the detected CLI generation.

## Update a range

```python
from online.sheets import update_range

update_range(
    docid="DOC_ID",
    sheet_id="SHEET_ID",
    start_row=1,
    start_column=0,
    rows=[
        ["Owner", "Status", "Count"],
        ["Jackson", "Open", 3],
    ],
    confirmed=True,
)
```

Rows are zero-indexed in the payload fields used by the wrapper. Confirm the starting coordinates and full matrix before writing.

Legacy CLI `0.1.x` cannot return current cell values through this wrapper. CLI `1.1+` uses `get_range()` for online reads. See the [migration note](/wecom-cli-migration) for the command map.
