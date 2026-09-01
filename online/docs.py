"""Online document helpers backed by legacy and current wecom-cli commands."""

from .wecom_cli import (
    WecomCliCompatibilityError,
    call_json,
    current_target_payload,
    doc_call,
    require_confirmation,
    resolve_generation,
    target_payload,
)


def create_document(name, confirmed=False, runner=None, cli_version=None):
    require_confirmation(confirmed, "create_document")
    if resolve_generation(cli_version=cli_version, runner=runner) == "current":
        return call_json(
            ["doc", "create"],
            {"doc_name": name, "doc_type": 3},
            runner=runner,
        )
    return doc_call("create_doc", {"doc_name": name, "doc_type": 3}, runner=runner)


def read_document(docid=None, url=None, content_type="markdown", runner=None, cli_version=None):
    if resolve_generation(cli_version=cli_version, runner=runner) != "current":
        raise WecomCliCompatibilityError("doc contents get requires wecom-cli 1.1+.")
    payload = current_target_payload(docid=docid, url=url)
    payload["content_type"] = content_type
    return call_json(["doc", "contents", "get"], payload, runner=runner)


def write_document_markdown(
    docid=None,
    url=None,
    content="",
    confirmed=False,
    runner=None,
    cli_version=None,
):
    require_confirmation(confirmed, "write_document_markdown")
    if resolve_generation(cli_version=cli_version, runner=runner) == "current":
        payload = current_target_payload(docid=docid, url=url)
        payload.update({"content": content, "content_type": "markdown"})
        return call_json(["doc", "contents", "overwrite"], payload, runner=runner)
    payload = target_payload(docid=docid, url=url)
    payload.update({"content": content, "content_type": 1})
    return doc_call("edit_doc_content", payload, runner=runner)


def create_smartpage(
    title,
    pages=None,
    confirmed=False,
    auto_file=False,
    runner=None,
    cli_version=None,
):
    require_confirmation(confirmed, "create_smartpage")
    if resolve_generation(cli_version=cli_version, runner=runner) == "current":
        if pages:
            raise WecomCliCompatibilityError(
                "Structured smartpage pages cannot be translated safely to wecom-cli 1.1+; "
                "use import_smartpage_markdown with a Markdown file."
            )
        if auto_file:
            raise WecomCliCompatibilityError("auto_file is only available with the legacy smartpage extension.")
        return call_json(["smartpage", "create"], {"name": title}, runner=runner)
    command = "+smartpage_create" if auto_file else "smartpage_create"
    return doc_call(command, {"title": title, "pages": pages or []}, runner=runner)


def import_smartpage_markdown(
    title,
    file_path,
    confirmed=False,
    runner=None,
    cli_version=None,
):
    require_confirmation(confirmed, "import_smartpage_markdown")
    if resolve_generation(cli_version=cli_version, runner=runner) != "current":
        raise WecomCliCompatibilityError("smartpage import requires wecom-cli 1.1+.")
    if not file_path:
        raise ValueError("file_path is required.")
    return call_json(
        ["smartpage", "import"],
        {"name": title, "file_path": str(file_path)},
        runner=runner,
    )
