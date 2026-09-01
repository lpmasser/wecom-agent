"""Online spreadsheet helpers for legacy and current wecom-cli commands."""

from numbers import Number

from .wecom_cli import (
    WecomCliCompatibilityError,
    call_json,
    current_target_payload,
    doc_call,
    require_confirmation,
    resolve_generation,
    target_payload,
)


def create_sheet(name, confirmed=False, runner=None, cli_version=None):
    require_confirmation(confirmed, "create_sheet")
    if resolve_generation(cli_version=cli_version, runner=runner) == "current":
        return call_json(["sheet", "create"], {"doc_name": name}, runner=runner)
    return doc_call("create_doc", {"doc_name": name, "doc_type": 4}, runner=runner)


def get_info(docid=None, url=None, runner=None, cli_version=None):
    generation = resolve_generation(cli_version=cli_version, runner=runner)
    payload = _target(docid, url, generation)
    if generation == "current":
        return call_json(["sheet", "get"], payload, runner=runner)
    return doc_call("sheet_get_info", payload, runner=runner)


def add_subsheet(
    docid=None,
    url=None,
    title="",
    row_count=100,
    column_count=20,
    index=None,
    confirmed=False,
    runner=None,
    cli_version=None,
):
    require_confirmation(confirmed, "add_subsheet")
    generation = resolve_generation(cli_version=cli_version, runner=runner)
    payload = _target(docid, url, generation)
    payload["sheet"] = {"title": title, "row_count": row_count, "column_count": column_count}
    if index is not None:
        payload["index"] = index
    if generation == "current":
        return call_json(["sheet", "subsheets", "add"], payload, runner=runner)
    return doc_call("sheet_add_sub", payload, runner=runner)


def delete_subsheet(
    docid=None,
    url=None,
    sheet_id="",
    confirmed=False,
    runner=None,
    cli_version=None,
):
    require_confirmation(confirmed, "delete_subsheet")
    generation = resolve_generation(cli_version=cli_version, runner=runner)
    payload = _target(docid, url, generation)
    payload["sheet_id"] = sheet_id
    if generation == "current":
        return call_json(["sheet", "subsheets", "delete"], payload, runner=runner)
    return doc_call("sheet_delete_sub", payload, runner=runner)


def append_row(
    docid=None,
    url=None,
    sheet_id="",
    values=None,
    confirmed=False,
    runner=None,
    cli_version=None,
):
    require_confirmation(confirmed, "append_row")
    generation = resolve_generation(cli_version=cli_version, runner=runner)
    payload = _target(docid, url, generation)
    payload.update({"sheet_id": sheet_id, "row": row_data(values or [], generation=generation)})
    if generation == "current":
        return call_json(["sheet", "rows", "append"], payload, runner=runner)
    return doc_call("sheet_append_data", payload, runner=runner)


def update_range(
    docid=None,
    url=None,
    sheet_id="",
    start_row=0,
    start_column=0,
    rows=None,
    confirmed=False,
    runner=None,
    cli_version=None,
):
    require_confirmation(confirmed, "update_range")
    generation = resolve_generation(cli_version=cli_version, runner=runner)
    payload = _target(docid, url, generation)
    payload.update(
        {
            "sheet_id": sheet_id,
            "grid_data": {
                "start_row": start_row,
                "start_column": start_column,
                "rows": [row_data(row, generation=generation) for row in (rows or [])],
            },
        }
    )
    if generation == "current":
        return call_json(["sheet", "contents", "update"], payload, runner=runner)
    return doc_call("sheet_update_range_data", payload, runner=runner)


def get_range(
    docid=None,
    url=None,
    sheet_id="",
    cell_range="",
    mode="default",
    runner=None,
    cli_version=None,
):
    generation = resolve_generation(cli_version=cli_version, runner=runner)
    if generation != "current":
        raise WecomCliCompatibilityError("sheet ranges get requires wecom-cli 1.1+.")
    payload = current_target_payload(docid=docid, url=url)
    payload.update({"sheet_id": sheet_id, "mode": mode})
    if mode == "default":
        if not cell_range:
            raise ValueError("cell_range is required when mode='default'.")
        payload["range"] = cell_range
    return call_json(["sheet", "ranges", "get"], payload, runner=runner)


def _target(docid, url, generation):
    if generation == "current":
        return current_target_payload(docid=docid, url=url)
    return target_payload(docid=docid, url=url)


def row_data(values, generation="legacy"):
    if isinstance(values, dict) and "values" in values:
        normalized = dict(values)
        normalized["values"] = [cell_data(value, generation=generation) for value in values["values"]]
        return normalized
    return {"values": [cell_data(value, generation=generation) for value in values]}


def cell_data(value, generation="legacy"):
    if isinstance(value, dict):
        if "data_type" in value or "cell_value" in value or "cell_format" in value:
            normalized = dict(value)
            if normalized.get("data_type") in {"FORMUAL", "FORMULA"}:
                normalized["data_type"] = "FORMULA" if generation == "current" else "FORMUAL"
            return normalized
        kind = value.get("type")
        if kind == "link":
            link = {"text": value.get("text"), "url": value.get("url")}
            if generation == "legacy":
                link["overwrite"] = value.get("overwrite", True)
            return {
                "data_type": "LINK",
                "cell_value": {"link": link},
            }
        if kind == "formula":
            formula_type = "FORMULA" if generation == "current" else "FORMUAL"
            return {"data_type": formula_type, "cell_value": {"formula": value.get("formula")}}
        if kind == "number":
            return {"data_type": "NUMBER", "cell_value": {"number": value.get("number")}}
        if kind == "text":
            return {"data_type": "TEXT", "cell_value": {"text": value.get("text", "")}}
        raise ValueError(f"Unsupported sheet cell dict: {value}")

    if isinstance(value, Number) and not isinstance(value, bool):
        return {"data_type": "NUMBER", "cell_value": {"number": value}}
    return {"data_type": "TEXT", "cell_value": {"text": "" if value is None else str(value)}}
