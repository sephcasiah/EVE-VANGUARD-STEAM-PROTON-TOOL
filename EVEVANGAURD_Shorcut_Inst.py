#!/usr/bin/env python3
"""
Eve: Vanguard Steam Shortcut "Installer"

DISCLAIMER
- This tool does NOT modify CCP's EVE Vanguard client, launcher, or any CCP software.
- All trademarks and copyrights for EVE, EVE Vanguard, and CCP products belong to CCP hf.
- This tool only edits your local Steam configuration (shortcuts/config .vdf files) to add a Non-Steam entry and set a Proton mapping.
- Use at your own risk; your mileage may vary. Do NOT contact CCP for support regarding this tool.
- For issues, contact the tool author/maintainer (not CCP).

Steps performed:
1) Locate Steam userdata and pick first profile (or --interactive to choose).
2) Backup and inject a Non-Steam "EVE Vanguard" shortcut into shortcuts.vdf.
3) (Optional) Watch for a running Vanguard process and capture args to LaunchOptions.
4) Compute non-Steam AppID and write Proton mapping (CompatToolMapping) to config.vdf.
5) Print results; user restarts Steam to apply.

Steps performed:
1) Locate Steam + profile, and auto-discover Vanguard prefix/exe (prompt only if missing).
2) Backup VDFs; inject Non-Steam "EVE Vanguard" shortcut.
3) Auto-capture Vanguard runtime args from the running client and set LaunchOptions.
4) Compute non-Steam AppID; set Proton mapping in config.vdf.
5) Persist config for future runs; write a verbose log file; print summary.

Quickstart:
  python3 -m pip install --user vdf psutil
  python3 vanguard_proton_helper.py --debug
"""
#!/usr/bin/env python3
import os, sys, argparse, shutil, time, json, zlib, traceback
from pathlib import Path
from datetime import datetime

try:
    import vdf
    import psutil
except Exception:
    print("Missing deps. Install with:\n  python3 -m pip install --user vdf psutil")
    sys.exit(1)

DEBUG = False
APP_NAME = "EVEVANGUARD_Shortcut_Inst"
DEFAULT_SHORTCUT_NAME = "EVE Vanguard"
DEFAULT_STEAM_ROOTS = [
    Path.home() / ".local" / "share" / "Steam",
    Path.home() / ".steam" / "steam",
    Path.home() / ".var" / "app" / "com.valvesoftware.Steam" / "data" / "Steam",
    Path("/usr/local/share/steam"),
]
DEFAULT_COMPATDATA_ID = "8500"
DEFAULT_REL_EXE = "drive_c/CCP/EVE/eve-vanguard/live/WindowsClient/start_protected_game.exe"
DEFAULT_PROTON = "proton_experimental"
DEFAULT_PRIORITY = 250

STATE_DIR = Path.home() / ".config" / "EVEVANGUARD_Shortcut_Inst"
LOGS_DIR = STATE_DIR / "logs"
CONF_PATH = STATE_DIR / "config.json"
LOG_PATH = None

DISCLAIMER = (
    "DISCLAIMER: This tool does NOT modify CCP's EVE Vanguard client/launcher. "
    "All rights for EVE / EVE Vanguard belong to CCP hf. "
    "It only edits local Steam config (shortcuts.vdf, config.vdf). "
    "Use at your own risk; contact the tool maintainer for support, not CCP."
)

def ensure_state_dirs():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

def new_log_file():
    global LOG_PATH
    ensure_state_dirs()
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    LOG_PATH = LOGS_DIR / f"run-{ts}.log"
    return LOG_PATH

def _write_log_line(s: str):
    if LOG_PATH:
        try:
            with LOG_PATH.open("a", encoding="utf-8") as fh:
                fh.write(s + "\n")
        except Exception:
            pass

def log(*a, **k):
    msg = " ".join(str(x) for x in a)
    if DEBUG:
        print("[DEBUG]", msg, **k)
    _write_log_line("[DEBUG] " + msg)

def info(*a, **k):
    msg = " ".join(str(x) for x in a)
    print(msg, **k)
    _write_log_line(msg)

def err(*a, **k):
    msg = " ".join(str(x) for x in a)
    print("ERROR:", msg, **k)
    _write_log_line("ERROR: " + msg)

def is_steam_running():
    for p in psutil.process_iter(attrs=("name","cmdline")):
        try:
            n = (p.info.get("name") or "").lower()
            if "steam" in n: return True
            if any("steam" in (c or "").lower() for c in (p.info.get("cmdline") or [])): return True
        except psutil.Error:
            pass
    return False

def find_userdata_roots(steam_root_hint: str|None):
    roots = []
    if steam_root_hint: roots.append(Path(steam_root_hint).expanduser())
    roots += DEFAULT_STEAM_ROOTS
    out = []
    for r in roots:
        ud = r / "userdata"
        if ud.is_dir():
            out.append((r, ud))
    return out

def find_profile_shortcuts(userdata_dir: Path):
    out = []
    for p in userdata_dir.iterdir():
        if p.is_dir() and p.name.isdigit():
            s = p / "config" / "shortcuts.vdf"
            if s.exists():
                out.append((p.name, s))
    return out

def backup(path: Path):
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bp = path.with_name(path.name + f".bak.{ts}")
    shutil.copy2(path, bp)
    log("Backup ->", bp)
    return bp

def read_shortcuts(path: Path):
    with path.open("rb") as fh:
        return vdf.binary_load(fh)

def write_shortcuts(path: Path, obj):
    with path.open("wb") as fh:
        vdf.binary_dump(obj, fh)

def find_numeric_container(node):
    if isinstance(node, dict):
        if node and all(isinstance(k, str) and k.isdigit() for k in node.keys()):
            return node
        for v in node.values():
            if isinstance(v, dict):
                got = find_numeric_container(v)
                if got: return got
    return None

def next_index(container: dict):
    nums = [int(k) for k in container.keys() if k.isdigit()]
    return str((max(nums)+1) if nums else 0)

def make_shortcut(name, exe, startdir, icon="", launch_opts=""):
    return {
        "appname": name,
        "exe": exe,
        "StartDir": startdir,
        "icon": icon or "",
        "ShortcutPath": "",
        "LaunchOptions": launch_opts,
        "IsHidden": 0,
        "AllowDesktopConfig": 1,
        "OpenVR": 0,
        "tags": {"0": "Non-Steam"},
    }

def inject_shortcut(shortcuts_path: Path, name, exe, startdir, icon="", launch_opts="", dry=False):
    obj = read_shortcuts(shortcuts_path)
    container = find_numeric_container(obj) or obj.get("shortcuts") or obj
    idx = next_index(container)
    entry = make_shortcut(name, exe, startdir, icon, launch_opts)
    container[idx] = entry
    if dry:
        info("DRY RUN: would add shortcut at index", idx)
        info(json.dumps(entry, indent=2))
        return idx, entry
    backup(shortcuts_path)
    write_shortcuts(shortcuts_path, obj)
    return idx, entry

def read_text_vdf(path: Path):
    with path.open("r", encoding="utf-8", errors="ignore") as fh:
        return vdf.load(fh)

def write_text_vdf(path: Path, obj):
    with path.open("w", encoding="utf-8") as fh:
        vdf.dump(obj, fh, pretty=True)

def compute_nonsteam_appid(exe: str, appname: str) -> int:
    key = (exe + appname).encode("utf-8")
    crc = zlib.crc32(key) & 0xffffffff
    appid = (crc | 0x80000000) & 0xffffffff
    return appid

def to_rungameid(appid: int) -> int:
    return ((appid & 0xffffffff) << 32) | 0x02000000

def scan_vanguard_args(timeout=120, poll=2):
    marker = "EVEVanguardClient-Win64-Shipping.exe"
    deadline = time.time() + timeout
    info("Waiting to capture Vanguard runtime args (launch Vanguard via EVE Online launcher)…")
    while time.time() < deadline:
        for p in psutil.process_iter(attrs=("pid","cmdline")):
            try:
                cmd = p.info.get("cmdline") or []
                if not cmd: continue
                joined = " ".join(cmd)
                if marker in joined:
                    tail = joined.split(marker,1)[1].strip()
                    if tail.startswith('"') and tail.endswith('"'):
                        tail = tail[1:-1]
                    info("Captured runtime args:", tail)
                    return tail
            except psutil.Error:
                pass
        time.sleep(poll)
    info("No args captured within timeout.")
    return ""

def set_compat_tool(config_vdf_path: Path, appid: int, tool_name: str, priority: int = DEFAULT_PRIORITY, dry=False):
    root = {}
    if config_vdf_path.exists():
        root = read_text_vdf(config_vdf_path)
    store = root.setdefault("InstallConfigStore", {}).setdefault("Software", {}).setdefault("Valve", {}).setdefault("Steam", {})
    mapping = store.setdefault("CompatToolMapping", {})
    key = str(appid)
    mapping[key] = {"name": tool_name, "config": "", "Priority": str(priority)}
    if dry:
        info("DRY RUN: would write CompatToolMapping in", str(config_vdf_path))
        info(f'{key}: {mapping[key]}')
        return
    backup(config_vdf_path)
    write_text_vdf(config_vdf_path, root)

def get_compat_tool(config_vdf_path: Path, appid: int):
    if not config_vdf_path.exists():
        return None
    try:
        root = read_text_vdf(config_vdf_path)
        mapping = root.get("InstallConfigStore", {}).get("Software", {}).get("Valve", {}).get("Steam", {}).get("CompatToolMapping", {})
        return mapping.get(str(appid))
    except Exception:
        return None

def auto_discover_prefix_and_exe(steam_root: Path):
    compat_root = steam_root / "steamapps" / "compatdata" / DEFAULT_COMPATDATA_ID / "pfx"
    exe_rel = DEFAULT_REL_EXE
    exe_abs = compat_root / exe_rel
    if exe_abs.exists():
        return str(compat_root), exe_rel
    candidate = None
    search_base = compat_root / "drive_c"
    if search_base.exists():
        for p in search_base.rglob("start_protected_game.exe"):
            candidate = p
            break
    if candidate:
        rel = candidate.relative_to(compat_root)
        return str(compat_root), str(rel).replace("\\","/")
    return None, None

def load_saved_config():
    if not CONF_PATH.exists():
        return {}
    try:
        return json.loads(CONF_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_config(d: dict):
    ensure_state_dirs()
    with CONF_PATH.open("w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=2)

def print_status(saved: dict, steam_root: Path|None, profile_id: str|None, shortcuts_path: Path|None, config_vdf: Path|None, name: str):
    info("=== Status ===")
    info("Saved config path:", str(CONF_PATH))
    info("Log file:", str(LOG_PATH) if LOG_PATH else "(none)")
    if saved:
        info("Saved config keys:", ", ".join(sorted(saved.keys())))
    if steam_root:
        info("Steam root:", str(steam_root))
    if profile_id:
        info("Profile ID:", profile_id)
    if shortcuts_path and shortcuts_path.exists():
        info("shortcuts.vdf:", str(shortcuts_path))
    if config_vdf and config_vdf.exists():
        info("config.vdf:", str(config_vdf))
    try:
        if shortcuts_path and shortcuts_path.exists():
            obj = read_shortcuts(shortcuts_path)
            container = find_numeric_container(obj) or obj.get("shortcuts") or obj
            for k, ent in container.items():
                if isinstance(ent, dict) and ent.get("appname") == name:
                    exe = ent.get("exe","")
                    appid = compute_nonsteam_appid(exe, name)
                    mapping = get_compat_tool(config_vdf, appid) if config_vdf else None
                    info(f"Detected shortcut index: {k}")
                    info(f"Computed AppID: {appid} (rungameid: {to_rungameid(appid)})")
                    info(f"LaunchOptions: {ent.get('LaunchOptions','')!r}")
                    info(f"Proton mapping: {mapping if mapping else '(none)'}")
                    break
    except Exception as e:
        err("Status check failed:", str(e))

def run_injection(args):
    if is_steam_running() and not args.dry_run:
        err("Please EXIT Steam before running.")
        sys.exit(1)

    saved = load_saved_config()
    log("Loaded saved config:", json.dumps(saved, indent=2) if saved else "(none)")

    steam_root = Path(saved.get("steam_root")) if saved.get("steam_root") else None
    profile_id = saved.get("profile_id")
    shortcuts_path = Path(saved.get("shortcuts_vdf")) if saved.get("shortcuts_vdf") else None
    config_vdf = Path(saved.get("config_vdf")) if saved.get("config_vdf") else None

    if not (steam_root and shortcuts_path and config_vdf and steam_root.exists() and shortcuts_path.exists() and config_vdf.exists()):
        roots = find_userdata_roots(args.steam_root)
        if not roots:
            if args.no_prompt:
                err("Steam userdata not found and prompting disabled.")
                sys.exit(2)
            info("Steam userdata not found automatically.")
            guess = input("Enter Steam root (e.g. ~/.local/share/Steam): ").strip()
            if not guess:
                sys.exit(2)
            roots = find_userdata_roots(guess)
        steam_root, userdata = roots[0]
        profiles = find_profile_shortcuts(userdata)
        if not profiles:
            err("No shortcuts.vdf found under:", str(userdata))
            sys.exit(3)
        profile_id, shortcuts_path = profiles[0]
        config_vdf = steam_root / "config" / "config.vdf"

    info(f"Using Steam profile {profile_id}")

    prefix = saved.get("prefix") or args.prefix
    exe_rel = saved.get("exe_rel") or (args.exe.replace("\\","/") if args.exe else None)

    if not prefix or not exe_rel:
        auto_prefix, auto_exe = auto_discover_prefix_and_exe(steam_root)
        if not prefix: prefix = auto_prefix
        if not exe_rel: exe_rel = auto_exe

    if not prefix or not exe_rel:
        if args.no_prompt:
            err("Could not auto-discover Vanguard path and prompting disabled.")
            sys.exit(5)
        info("Could not auto-discover Vanguard path.")
        prefix = input(f"Enter Vanguard Proton prefix: ").strip()
        exe_rel = input(f"Enter path to Vanguard exe relative to prefix: ").strip()

    exe_rel = exe_rel.replace("\\","/")
    startdir = str((Path(prefix).expanduser() / Path(exe_rel).parent).resolve())

    idx, entry = inject_shortcut(shortcuts_path, args.name, exe_rel, startdir, args.icon, "", args.dry_run)
    info(f"Shortcut injected (index {idx}) at {shortcuts_path}")

    if not args.dry_run:
        tail = scan_vanguard_args(timeout=args.timeout)
        if tail:
            obj = read_shortcuts(shortcuts_path)
            container = find_numeric_container(obj) or obj.get("shortcuts") or obj
            if idx in container:
                container[idx]["LaunchOptions"] = tail
                backup(shortcuts_path)
                write_shortcuts(shortcuts_path, obj)
                info("Patched LaunchOptions =", tail)
        else:
            info("Proceeding without LaunchOptions (none captured).")

    appid = compute_nonsteam_appid(entry["exe"], entry["appname"])
    rungameid = to_rungameid(appid)
    info(f"Computed AppID: {appid}  (rungameid: {rungameid})")
    set_compat_tool(config_vdf, appid, args.proton, args.priority, args.dry_run)
    info(f"Set CompatToolMapping for AppID {appid} -> '{args.proton}' in {config_vdf}")

    state = {
        "steam_root": str(steam_root),
        "profile_id": profile_id,
        "shortcuts_vdf": str(shortcuts_path),
        "config_vdf": str(config_vdf),
        "prefix": str(prefix),
        "exe_rel": str(exe_rel),
        "shortcut_name": args.name,
        "appid": appid,
        "proton_tool": args.proton,
        "priority": args.priority
    }
    save_config(state)
    info(f"Saved config -> {CONF_PATH}")
    info("Done. Restart Steam to load the new shortcut and Proton mapping.")
    info(f"Log file: {LOG_PATH}")

def run_status():
    saved = load_saved_config()
    steam_root = Path(saved["steam_root"]) if "steam_root" in saved else None
    shortcuts_path = Path(saved["shortcuts_vdf"]) if "shortcuts_vdf" in saved else None
    config_vdf = Path(saved["config_vdf"]) if "config_vdf" in saved else None
    profile_id = saved.get("profile_id")
    print_status(saved, steam_root, profile_id, shortcuts_path, config_vdf, saved.get("shortcut_name", DEFAULT_SHORTCUT_NAME))
    info(f"Log file: {LOG_PATH}")

def main():
    global DEBUG, LOG_PATH
    LOG_PATH = new_log_file()

    ap = argparse.ArgumentParser(description=f"{APP_NAME}: inject Steam shortcut, auto-capture args, set Proton; writes logs + config.")
    ap.add_argument("--steam-root", help="Steam root (e.g. ~/.local/share/Steam)")
    ap.add_argument("--prefix", help="Proton prefix root")
    ap.add_argument("--exe", help="Path inside prefix to Vanguard exe")
    ap.add_argument("--name", default=DEFAULT_SHORTCUT_NAME, help="Shortcut name")
    ap.add_argument("--icon", default="", help="Icon path")
    ap.add_argument("--proton", default=DEFAULT_PROTON, help="Steam Play tool")
    ap.add_argument("--priority", type=int, default=DEFAULT_PRIORITY, help="Compat tool priority")
    ap.add_argument("--timeout", type=int, default=120, help="Seconds to wait when capturing args")
    ap.add_argument("--dry-run", action="store_true", help="Preview only")
    ap.add_argument("--no-prompt", action="store_true", help="Disable prompts; fail if discovery incomplete")
    ap.add_argument("--status", action="store_true", help="Show current shortcut/mapping and exit")
    ap.add_argument("--debug", action="store_true", help="Verbose console output")
    args = ap.parse_args()
    DEBUG = args.debug

    info(DISCLAIMER)
    info(f"{APP_NAME} starting…")
    info(f"Log file: {LOG_PATH}")

    try:
        if args.status:
            run_status()
            return
        run_injection(args)
    except KeyboardInterrupt:
        err("Interrupted by user.")
    except Exception as e:
        err("Unhandled error:", str(e))
        tb = traceback.format
