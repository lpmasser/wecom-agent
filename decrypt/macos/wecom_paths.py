"""企业微信(macOS) 路径自动探测 —— 不硬编码用户名/profile，开箱即用、可分发。

profile 目录名是每账号一串 hash；本模块自动在沙盒容器里找含 Messages1 的那个
(可用环境变量 WECOM_PROFILE 指定)。
"""
import functools
import glob
import os

CONTAINER = os.path.expanduser("~/Library/Containers/com.tencent.WeWorkMac/Data")
_PROFILES = os.path.join(CONTAINER, "Documents", "Profiles")
_HERE = os.path.dirname(os.path.abspath(__file__))
CHAT_DATABASES = ("Messages1/Info.db", "Messages1/Session.db")


@functools.lru_cache(maxsize=1)
def profile_dir():
    env = os.environ.get("WECOM_PROFILE")
    if env:
        env = os.path.expanduser(env)
        p = env if os.path.isdir(env) else os.path.join(_PROFILES, env)
        if os.path.isdir(p):
            return p
        raise SystemExit("WECOM_PROFILE 指定的目录不存在；请修正该配置")
    cands = [
        d for d in glob.glob(os.path.join(_PROFILES, "*"))
        if os.path.isdir(d) and os.path.isdir(os.path.join(d, "Messages1"))
    ]
    if not cands:
        raise SystemExit(f"未找到企业微信 profile (在 {_PROFILES})；企微是否登录过？")
    if len(cands) > 1:
        raise SystemExit("发现多个企业微信账号；请用 WECOM_PROFILE 指定要读取的 profile 目录")
    return cands[0]


def info_db():
    return os.path.join(profile_dir(), "Messages1", "Info.db")


def session_db():
    return os.path.join(profile_dir(), "Messages1", "Session.db")


def caches():
    return os.environ.get("WECOM_CACHE_DIR") or os.path.join(profile_dir(), "Caches")


def state_dir():
    """Private runtime root, separated by the selected native profile."""
    base = os.path.expanduser(os.environ.get("WECOM_STATE_DIR", "~/.local/share/wecom-agent"))
    return os.path.join(base, os.path.basename(os.path.normpath(profile_dir())))


def keys_file():
    explicit = os.environ.get("WECOM_KEYS_FILE")
    if explicit:
        return os.path.expanduser(explicit)
    legacy = os.path.join(_HERE, "wxwork_keys.json")
    if not os.environ.get("WECOM_STATE_DIR") and os.path.isfile(legacy):
        return legacy
    return os.path.join(state_dir(), "wxwork_keys.json")


def decrypted(*parts):
    """Honor explicit paths; reuse existing legacy snapshots without moving data."""
    base = os.environ.get("WECOM_DECRYPTED_DIR")
    if not base:
        legacy = os.path.join(_HERE, "decrypted")
        base = legacy if not os.environ.get("WECOM_STATE_DIR") and os.path.isdir(legacy) else os.path.join(state_dir(), "decrypted")
    return os.path.join(os.path.expanduser(base), *parts)
