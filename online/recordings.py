# /// script
# requires-python = ">=3.10"
# dependencies = ["browser-cookie3==0.20.1"]
# ///
"""Download an authorized WeCom meeting recording over HTTP on macOS.

Uses the existing WeCom CEF session and the recording page's download API.
No screen automation, browser cache URL, login mutation, or token export.
"""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.parse import parse_qs, quote, urlencode, urlsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener
import uuid

import browser_cookie3


ORIGIN = "https://meeting.tencent.com"
API = ORIGIN + "/wemeet-tapi/v2/meetlog/public/record-detail/"
CEF_ROOT = Path.home() / "Library/Containers/com.tencent.WeWorkMac/Data/Documents/cefcache"


def client_session(profile):
    if sys.platform != "darwin":
        raise RuntimeError("This session reader supports macOS WeCom only")
    if profile:
        cookie_file = CEF_ROOT / profile / "Cookies"
    else:
        candidates = list(CEF_ROOT.glob("wew_*/Cookies"))
        if len(candidates) != 1:
            raise RuntimeError("Select the WeCom CEF account with --profile")
        cookie_file = candidates[0]
    if not cookie_file.is_file():
        raise RuntimeError("The selected WeCom cookie profile does not exist")

    # WeCom 5.0.12 uses Chromium's mock-keychain format for this CEF store.
    # Only the meeting origin is read; credentials remain in process memory.
    browser_cookie3.CHROMIUM_DEFAULT_PASSWORD = b"mock_password"
    jar = browser_cookie3.chromium(
        cookie_file=str(cookie_file), domain_name="meeting.tencent.com"
    )
    values = {cookie.name: cookie.value for cookie in jar}
    if not all(values.get(key) for key in ("we_meet_token", "app_uid", "corp_id")):
        raise RuntimeError("An existing signed-in WeCom recording session is required")

    commands = subprocess.check_output(["ps", "-axo", "command"], text=True)
    user_agent = None
    for line in commands.splitlines():
        if "企业微信.app/" not in line:
            continue
        match = re.search(r"--user-agent=(.+?)(?=\s--|$)", line)
        if match:
            user_agent = match.group(1).strip('"')
            break
    if not user_agent:
        raise RuntimeError("Keep the signed-in WeCom client running")
    version_match = re.search(r"wxwork/([\d.]+)", user_agent)
    if not version_match:
        raise RuntimeError("The running client does not expose a WeCom version")
    return build_opener(HTTPCookieProcessor(jar)), user_agent, version_match.group(1)


def client_query(user_agent, version):
    now = str(int(time.time() * 1000))
    # Match the web client + WeCom bridge merge. Repeated and empty parameters
    # are significant: flattening them changed downloadable=true to false.
    return [
        ("c_app_id", "1400143280"), ("c_os_model", "web"), ("c_os", "web"),
        ("c_os_version", "1"), ("c_timestamp", now), ("c_nonce", uuid.uuid4().hex),
        ("c_app_version", "1"), ("c_instance_id", "5"), ("rnds", uuid.uuid4().hex),
        ("c_district", "0"), ("c_instance_id", "5"), ("c_os_model", "web"),
        ("c_os_version", quote(user_agent, safe="")), ("c_timestamp", now),
        ("c_app_id", ""), ("c_app_uid", ""), ("c_platform", "0"), ("c_token", ""),
        ("c_app_version", version), ("platform", "Web"), ("app_id", ""),
        ("c_nonce", uuid.uuid4().hex), ("c_os", "web"), ("c_sdk_id", "16366985372"),
    ]


def meeting_share(meeting_id, cli):
    request = json.dumps({"meeting_ids": [{"meeting_id": meeting_id}]})
    result = subprocess.run(
        [cli, "meeting", "get", "--json", request], capture_output=True, text=True
    )
    if result.returncode:
        raise RuntimeError(f"wecom-cli meeting get failed ({result.returncode})")
    meetings = json.loads(result.stdout).get("meetings", [])
    meeting = next((m for m in meetings if m.get("meeting_id") == meeting_id), None)
    if not meeting or not meeting.get("record_url"):
        raise RuntimeError("No recording link was returned for this meeting")
    url = meeting["record_url"]
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "meeting.tencent.com":
        raise RuntimeError("Unexpected recording link origin")
    share_ids = parse_qs(parsed.query).get("id", [])
    if len(share_ids) != 1:
        raise RuntimeError("The recording link has no unique share identifier")
    return share_ids[0], url


def download(meeting_id, record_file_id, output, profile, cli):
    if output.exists():
        raise RuntimeError("The output file already exists")
    share_id, referer = meeting_share(meeting_id, cli)
    opener, user_agent, version = client_session(profile)
    headers = {"User-Agent": user_agent, "Referer": referer}

    def api(name, params):
        query = client_query(user_agent, version) + list(params.items())
        with opener.open(Request(API + name + "?" + urlencode(query), headers=headers), timeout=30) as response:
            result = json.load(response)
        if result.get("code") != 0:
            raise RuntimeError(f"Recording API rejected {name} (code={result.get('code')})")
        return result["data"]

    params = {"record_id": record_file_id, "auth_share_id": share_id, "activity_uid": ""}
    files = api("get-multi-record-file", params)["files"]
    target = next((f for f in files if f.get("resource_id") == record_file_id and f.get("resource_type") == 0), None)
    if target is None or target.get("downloadable") is not True:
        raise RuntimeError("The server does not authorize downloading this video")
    size = int(target["size"])
    signed = api("sign-multi-record-file", dict(params, resource_id=record_file_id, resource_type=0))
    media_url = signed["url"]
    parsed = urlsplit(media_url)
    if parsed.scheme != "https" or not (parsed.hostname or "").endswith(".meeting.tencent.com"):
        raise RuntimeError("Unexpected recording media origin")

    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    partial = output.with_name(output.name + ".part")
    written = 0
    destination = partial.open("xb")
    try:
        with destination, opener.open(Request(media_url, headers=dict(headers, Range="bytes=0-")), timeout=60) as response:
            while chunk := response.read(1024 * 1024):
                destination.write(chunk)
                written += len(chunk)
        if written != size:
            raise RuntimeError(f"Incomplete video: expected {size} bytes, received {written}")
        partial.rename(output)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return {"meeting_id": meeting_id, "record_file_id": record_file_id, "bytes": written, "output": str(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--meeting-id", required=True, help="WeCom mt... meeting ID")
    parser.add_argument("--record-file-id", required=True, help="Cloud video record_file_id from tmeet")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", help="WeCom CEF profile directory name, required with multiple accounts")
    parser.add_argument("--wecom-cli", default="wecom-cli")
    args = parser.parse_args()
    os.umask(0o077)
    try:
        result = download(args.meeting_id, args.record_file_id, args.output.expanduser().resolve(), args.profile, args.wecom_cli)
    except Exception as error:
        # Network exception text may contain signed URLs. Do not print it.
        message = str(error) if isinstance(error, RuntimeError) else type(error).__name__
        print(json.dumps({"error": message}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
