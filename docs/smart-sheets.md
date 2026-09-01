---
title: Smart Sheets
description: Manage smart-sheet containers, fields, and records through confirmed WecomTeam CLI operations.
---

# Smart Sheets

`online.smartsheets` routes operations across the legacy CLI `0.1.x` flat document commands and the current CLI `1.1+` nested `smartsheet` service.

Run `python3 -m online.selfcheck` before using this module. The report shows the detected generation and read/write wrapper coverage.

## Create and inspect

```python
from online.smartsheets import create_smartsheet, get_fields, get_sheets

created = create_smartsheet("Localization Tracker", confirmed=True)
sheets = get_sheets(docid="DOC_ID")
fields = get_fields(docid="DOC_ID", sheet_id="SHEET_ID")
```

`get_sheets()` and `get_fields()` are read-only. Legacy create uses document type `10`; current create uses `smartsheet create`.

## Manage child sheets

```python
from online.smartsheets import add_sheet, delete_sheet, update_sheet

added = add_sheet(docid="DOC_ID", title="Backlog", confirmed=True)
renamed = update_sheet(
    docid="DOC_ID",
    sheet_id="SHEET_ID",
    title="Ready",
    confirmed=True,
)
removed = delete_sheet(
    docid="DOC_ID",
    sheet_id="SHEET_ID",
    confirmed=True,
)
```

## Manage fields

Field payloads are passed to the CLI without inventing a schema. Build them from the installed command's schema output:

```bash
wecom-cli smartsheet fields add --schema
```

```python
from online.smartsheets import add_fields, delete_fields, update_fields

add_fields(
    docid="DOC_ID",
    sheet_id="SHEET_ID",
    fields=[{"field_title": "Status", "field_type": "TEXT"}],
    confirmed=True,
)

update_fields(
    docid="DOC_ID",
    sheet_id="SHEET_ID",
    fields=[{"field_id": "FIELD_ID", "field_title": "Workflow Status"}],
    confirmed=True,
)

delete_fields(
    docid="DOC_ID",
    sheet_id="SHEET_ID",
    field_ids=["FIELD_ID"],
    confirmed=True,
)
```

## Read and manage records

Record reads require CLI `1.1+`:

```python
from online.smartsheets import get_records

page = get_records(
    docid="DOC_ID",
    sheet_id="SHEET_ID",
    limit=100,
    key_type="field_title",
)
```

Use the returned cursor for the next page. Legacy CLI `0.1.x` does not expose record reads and raises a compatibility error.

```python
from online.smartsheets import add_records, delete_records, update_records

add_records(
    docid="DOC_ID",
    sheet_id="SHEET_ID",
    records=[{"values": {"Status": "Ready"}}],
    confirmed=True,
)

update_records(
    docid="DOC_ID",
    sheet_id="SHEET_ID",
    records=[{"record_id": "RECORD_ID", "values": {"Status": "Done"}}],
    key_type="FIELD_TITLE",
    confirmed=True,
)

delete_records(
    docid="DOC_ID",
    sheet_id="SHEET_ID",
    record_ids=["RECORD_ID"],
    confirmed=True,
)
```

`auto_file=True` is only supported by the legacy `+smartsheet_*_auto_file` extension. Current CLI calls reject this flag instead of silently ignoring it.
