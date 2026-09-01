---
title: Online Documents
description: Create, read, and replace WeCom document content across supported CLI generations.
---

# Online Documents

The `online.docs` module translates normal-document operations across legacy CLI `0.1.x` and the current `1.1+` nested command model. Current releases support latest-body reads plus smart-page creation and Markdown import. Structured legacy smart-page payloads remain available only on `0.1.x`.

## Authenticate and inspect support

```bash
npm install -g @wecom/cli
wecom-cli auth init
wecom-cli auth show --status
python3 -m online.selfcheck
```

An authenticated session can still lack an API category. Treat an enterprise permission error as a capability boundary instead of retrying the same command.

## Create a normal document

```python
from online.docs import create_document

created = create_document("Release Checklist", confirmed=True)
```

`create_document()` sends legacy `doc create_doc` or current `doc create`, both with document type `3`.

## Read latest document content

```python
from online.docs import read_document

latest = read_document(docid="DOC_ID", content_type="markdown")
```

This requires `wecom-cli 1.1+` and calls `doc contents get`. Legacy `0.1.x` raises a compatibility error before making a request.

## Replace document content

Target a document by either `docid` or `url`, never both:

```python
from online.docs import write_document_markdown

updated = write_document_markdown(
    docid="DOC_ID",
    content="# Release Checklist\n\n- Verify build\n- Publish notes",
    confirmed=True,
)
```

The wrapper sends legacy `doc edit_doc_content` or current `doc contents overwrite`. This is a replacement operation, so confirm the full resulting body before execution.

## Create a smart page

```python
from online.docs import create_smartpage

result = create_smartpage(
    "Project Hub",
    pages=[],
    confirmed=True,
)
```

On CLI `1.1+`, `pages` must be empty because the current create API only accepts a title. A non-empty structured legacy payload is rejected before execution.

Import an existing Markdown file when the page needs initial content:

```python
from online.docs import import_smartpage_markdown

result = import_smartpage_markdown(
    "Project Hub",
    "/path/to/project-hub.md",
    confirmed=True,
)
```

## Local document fallback

Use `online.local_docs` when current online reads are unavailable because of a legacy CLI, permissions, or an offline workflow. It can inspect files already cached, downloaded, or opened on the current device:

```python
from online.local_docs import read_path, search

one = read_path("~/Downloads/Release Checklist.docx")
matches = search("Release Checklist", max_results=5)
```

Every result identifies itself as `local-cache-fallback` and records that the file may be stale relative to the online document. A missing match means the file was not found in the searched local roots; it does not prove that the online document does not exist.

## Default search roots

When `WECOM_LOCAL_DOC_ROOTS` is unset, the fallback checks the WeCom cache when available and then the user's Downloads, Documents, and Desktop directories. Set custom roots with the platform path separator:

```bash
export WECOM_LOCAL_DOC_ROOTS="$HOME/WorkDocs:$HOME/Downloads"
```
