"""Smart-sheet helpers backed by legacy and current wecom-cli commands."""

from .wecom_cli import (
    WecomCliCompatibilityError,
    call_json,
    current_target_payload,
    doc_call,
    require_confirmation,
    resolve_generation,
    target_payload,
)


def _current(cli_version=None, runner=None):
    return resolve_generation(cli_version=cli_version, runner=runner) == "current"


def _legacy_call(command, payload, runner=None):
    return doc_call(command, payload, runner=runner)


def _current_call(resource, command, payload, runner=None):
    return call_json(["smartsheet", resource, command], payload, runner=runner)


def _current_target(docid=None, url=None):
    return current_target_payload(docid=docid, url=url)


def _required(value, name):
    if not value:
        raise ValueError(f"{name} is required.")


def _current_key_type(value):
    return {"FIELD_TITLE": "field_title", "FIELD_ID": "field_id"}.get(value, value)


def create_smartsheet(name, confirmed=False, runner=None, cli_version=None):
    require_confirmation(confirmed, "create_smartsheet")
    if _current(cli_version, runner):
        return call_json(["smartsheet", "create"], {"name": name}, runner=runner)
    return _legacy_call("create_doc", {"doc_name": name, "doc_type": 10}, runner)


def get_sheets(docid=None, url=None, runner=None, cli_version=None):
    if _current(cli_version, runner):
        return _current_call("sheets", "list", _current_target(docid, url), runner)
    return _legacy_call(
        "smartsheet_get_sheet",
        target_payload(docid=docid, url=url),
        runner,
    )


def add_sheet(docid=None, url=None, title=None, confirmed=False, runner=None, cli_version=None):
    require_confirmation(confirmed, "add_sheet")
    if _current(cli_version, runner):
        _required(title, "title")
        payload = _current_target(docid, url)
        payload["sheet_title"] = title
        return _current_call("sheets", "add", payload, runner)
    payload = target_payload(docid=docid, url=url)
    if title:
        payload["properties"] = {"title": title}
    return _legacy_call("smartsheet_add_sheet", payload, runner)


def update_sheet(docid=None, url=None, sheet_id="", title="", confirmed=False, runner=None, cli_version=None):
    require_confirmation(confirmed, "update_sheet")
    if _current(cli_version, runner):
        _required(sheet_id, "sheet_id")
        _required(title, "title")
        payload = _current_target(docid, url)
        payload.update({"sheet_id": sheet_id, "new_sheet_title": title})
        return _current_call("sheets", "update", payload, runner)
    payload = target_payload(docid=docid, url=url)
    payload["properties"] = {"sheet_id": sheet_id, "title": title}
    return _legacy_call("smartsheet_update_sheet", payload, runner)


def delete_sheet(docid=None, url=None, sheet_id="", confirmed=False, runner=None, cli_version=None):
    require_confirmation(confirmed, "delete_sheet")
    if _current(cli_version, runner):
        _required(sheet_id, "sheet_id")
        payload = _current_target(docid, url)
        payload["sheet_id"] = sheet_id
        return _current_call("sheets", "delete", payload, runner)
    payload = target_payload(docid=docid, url=url)
    payload["sheet_id"] = sheet_id
    return _legacy_call("smartsheet_delete_sheet", payload, runner)


def get_fields(docid=None, url=None, sheet_id="", runner=None, cli_version=None):
    if _current(cli_version, runner):
        _required(sheet_id, "sheet_id")
        payload = _current_target(docid, url)
        payload["sheet_id"] = sheet_id
        return _current_call("fields", "list", payload, runner)
    payload = target_payload(docid=docid, url=url)
    payload["sheet_id"] = sheet_id
    return _legacy_call("smartsheet_get_fields", payload, runner)


def add_fields(docid=None, url=None, sheet_id="", fields=None, confirmed=False, runner=None, cli_version=None):
    require_confirmation(confirmed, "add_fields")
    if _current(cli_version, runner):
        _required(sheet_id, "sheet_id")
        payload = _current_target(docid, url)
        payload.update({"sheet_id": sheet_id, "fields": fields or []})
        return _current_call("fields", "add", payload, runner)
    payload = target_payload(docid=docid, url=url)
    payload.update({"sheet_id": sheet_id, "fields": fields or []})
    return _legacy_call("smartsheet_add_fields", payload, runner)


def update_fields(docid=None, url=None, sheet_id="", fields=None, confirmed=False, runner=None, cli_version=None):
    require_confirmation(confirmed, "update_fields")
    if _current(cli_version, runner):
        _required(sheet_id, "sheet_id")
        payload = _current_target(docid, url)
        payload.update({"sheet_id": sheet_id, "fields": fields or []})
        return _current_call("fields", "update", payload, runner)
    payload = target_payload(docid=docid, url=url)
    payload.update({"sheet_id": sheet_id, "fields": fields or []})
    return _legacy_call("smartsheet_update_fields", payload, runner)


def delete_fields(docid=None, url=None, sheet_id="", field_ids=None, confirmed=False, runner=None, cli_version=None):
    require_confirmation(confirmed, "delete_fields")
    if _current(cli_version, runner):
        _required(sheet_id, "sheet_id")
        payload = _current_target(docid, url)
        payload.update(
            {
                "sheet_id": sheet_id,
                "fields": [{"field_id": field_id} for field_id in field_ids or []],
            }
        )
        return _current_call("fields", "delete", payload, runner)
    payload = target_payload(docid=docid, url=url)
    payload.update({"sheet_id": sheet_id, "field_ids": field_ids or []})
    return _legacy_call("smartsheet_delete_fields", payload, runner)


def add_records(docid=None, url=None, sheet_id="", records=None, confirmed=False, auto_file=False, runner=None, cli_version=None):
    require_confirmation(confirmed, "add_records")
    if _current(cli_version, runner):
        if auto_file:
            raise WecomCliCompatibilityError("auto_file is only available with the legacy smart-sheet extension.")
        _required(sheet_id, "sheet_id")
        payload = _current_target(docid, url)
        payload.update({"sheet_id": sheet_id, "records": records or []})
        return _current_call("records", "add", payload, runner)
    payload = target_payload(docid=docid, url=url)
    payload.update({"sheet_id": sheet_id, "records": records or []})
    command = "+smartsheet_add_records_auto_file" if auto_file else "smartsheet_add_records"
    return _legacy_call(command, payload, runner)


def update_records(docid=None, url=None, sheet_id="", records=None, key_type=None, confirmed=False, auto_file=False, runner=None, cli_version=None):
    require_confirmation(confirmed, "update_records")
    if _current(cli_version, runner):
        if auto_file:
            raise WecomCliCompatibilityError("auto_file is only available with the legacy smart-sheet extension.")
        _required(sheet_id, "sheet_id")
        payload = _current_target(docid, url)
        payload.update({"sheet_id": sheet_id, "records": records or []})
        if key_type:
            payload["key_type"] = _current_key_type(key_type)
        return _current_call("records", "update", payload, runner)
    payload = target_payload(docid=docid, url=url)
    payload.update({"sheet_id": sheet_id, "records": records or []})
    if key_type:
        payload["key_type"] = key_type
    command = "+smartsheet_update_records_auto_file" if auto_file else "smartsheet_update_records"
    return _legacy_call(command, payload, runner)


def delete_records(docid=None, url=None, sheet_id="", record_ids=None, confirmed=False, runner=None, cli_version=None):
    require_confirmation(confirmed, "delete_records")
    if _current(cli_version, runner):
        _required(sheet_id, "sheet_id")
        payload = _current_target(docid, url)
        payload.update(
            {
                "sheet_id": sheet_id,
                "records": [{"record_id": record_id} for record_id in record_ids or []],
            }
        )
        return _current_call("records", "delete", payload, runner)
    payload = target_payload(docid=docid, url=url)
    payload.update({"sheet_id": sheet_id, "record_ids": record_ids or []})
    return _legacy_call("smartsheet_delete_records", payload, runner)


def get_records(
    docid=None,
    url=None,
    sheet_id="",
    limit=100,
    cursor=None,
    start=None,
    key_type=None,
    field_ids=None,
    field_titles=None,
    view_id=None,
    filter_spec=None,
    sort=None,
    runner=None,
    cli_version=None,
):
    if not _current(cli_version, runner):
        raise WecomCliCompatibilityError("smartsheet records list requires wecom-cli 1.1+.")
    _required(sheet_id, "sheet_id")
    payload = _current_target(docid, url)
    payload.update({"sheet_id": sheet_id, "limit": limit})
    optional = {
        "cursor": cursor,
        "start": start,
        "key_type": _current_key_type(key_type),
        "field_ids": field_ids,
        "field_titles": field_titles,
        "view_id": view_id,
        "filter_spec": filter_spec,
        "sort": sort,
    }
    payload.update({key: value for key, value in optional.items() if value is not None})
    return _current_call("records", "list", payload, runner)
