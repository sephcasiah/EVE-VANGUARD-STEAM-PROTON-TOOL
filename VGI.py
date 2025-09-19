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
import os, sys, argparse, shutil, time, json, traceback, random
from pathlib import Path
from datetime import datetime

try:
    import vdf
    import psutil
except Exception:
    print("Missing deps. Install with:\n  python3 -m pip install --user vdf psutil")
    sys.exit(1)

DEBUG = False
APP_NAME = "VGI"
DEFAULT_SHORTCUT_NAME = "EVE Vanguard"
DEFAULT_STEAM_ROOTS = [
    Path.home() / ".local" / "share" / "Steam",
    Path.home() / ".steam" / "steam",
    Path.home() / ".var" / "app" / "com.valvesoftware.Steam" / "data" / "Steam",
    Path("/usr/local/share/steam"),
]
DEFAULT_COMPATDATA_ID = "8500"
DEFAULT_PROTON = "proton_experimental"
DEFAULT_PRIORITY = 250
EAC_EXE_NAME = "start_protected_game.exe"
SHIPPING_EXE_NAME = "EVEVanguardClient-Win64-Shipping.exe"

STATE_DIR = Path.home() / ".config" / "VGI"
LOGS_DIR = STATE_DIR / "logs"
CONF_PATH = STATE_DIR / "config.json"
LOG_PATH = None

DISCLAIMER = ("DISCLAIMER: This tool does NOT modify CCP software. It edits local Steam config only. "
              "All rights belong to CCP hf. Use at your own risk; do not contact CCP for support.")

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

def log(*a):
    msg = " ".join(str(x) for x in a)
    if DEBUG: print("[DEBUG]", msg)
    _write_log_line("[DEBUG] " + msg)

def info(*a):
    msg = " ".join(str(x) for x in a)
    print(msg); _write_log_line(msg)

def err(*a):
    msg = " ".join(str(x) for x in a)
    print("ERROR:", msg); _write_log_line("ERROR: " + msg)


def is_steam_running(_hint=None):
    names = {"steam","steam.sh"}
    for p in psutil.process_iter(attrs=("name","exe")):
        try:
            n = (p.info.get("name") or "").lower()
            base = os.path.basename((p.info.get("exe") or "")).lower()
            if n in names or base in names: return True
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
        if ud.is_dir(): out.append((r, ud))
    return out

def find_profile_shortcuts(userdata_dir: Path):
    out = []
    for p in userdata_dir.iterdir():
        if p.is_dir() and p.name.isdigit():
            out.append((p.name, p / "config" / "shortcuts.vdf"))
    return out

def read_library_folders(steam_root: Path):
    libs = {steam_root}
    lf = steam_root / "config" / "libraryfolders.vdf"
    if lf.exists():
        try:
            data = read_text_vdf(lf)
            for k, v in (data.get("libraryfolders") or data).items():
                if isinstance(v, dict) and "path" in v:
                    p = Path(v["path"])
                    if (p / "steamapps").exists(): libs.add(p)
        except Exception as e:
            log("libraryfolders parse failed:", e)
    return list(libs)

def search_compat_pfx_across_libraries(library_roots, compat_id: str):
    for root in library_roots:
        pfx = root / "steamapps" / "compatdata" / compat_id / "pfx"
        if pfx.is_dir(): return pfx
    return None

def backup(path: Path):
    if not path.exists(): return None
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bp = path.with_name(path.name + f".bak.{ts}")
    shutil.copy2(path, bp); log("Backup ->", bp); return bp

def read_shortcuts(path: Path):
    if not path.parent.exists(): path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists(): return {"shortcuts": {}}
    with path.open("rb") as fh: return vdf.binary_load(fh)

def write_shortcuts(path: Path, obj):
    if not path.parent.exists(): path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh: vdf.binary_dump(obj, fh)

def read_text_vdf(path: Path):
    if not path.exists(): return {}
    with path.open("r", encoding="utf-8", errors="ignore") as fh: return vdf.load(fh)

def write_text_vdf(path: Path, obj):
    if not path.parent.exists(): path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh: vdf.dump(obj, fh, pretty=True)

def find_eac_exe_under_pfx(pfx: Path):
    """Return relative path (from pfx) to start_protected_game.exe, or None."""
    search_base = pfx / "drive_c"
    if not search_base.exists(): return None
    for p in search_base.rglob(EAC_EXE_NAME):
        return str(p.relative_to(pfx)).replace("\\","/")
    return None

def validate_prefix_and_eac(prefix: str|Path, exe_rel: str|None):
    try:
        prefix = Path(prefix).expanduser()
        if not (prefix.is_dir() and (prefix / "drive_c").exists()): return False
        if not exe_rel or not exe_rel.endswith(EAC_EXE_NAME): return False
        return (prefix / exe_rel).is_file()
    except Exception:
        return False

def auto_discover_eac(steam_root: Path, compat_id: str):

    libs = read_library_folders(steam_root); log("Library roots:", ", ".join(str(x) for x in libs))
    pfx = search_compat_pfx_across_libraries(libs, compat_id)
    if not pfx: return None, None
    eac_rel = find_eac_exe_under_pfx(pfx)
    if eac_rel: return str(pfx), eac_rel
    return None, None

def find_numeric_container(node):
    if isinstance(node, dict):
        if node and all(isinstance(k, str) and k.isdigit() for k in node.keys()): return node
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
        "appid": random.randint(-2147483648, -1),
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
    container = find_numeric_container(obj) or obj.get("shortcuts")
    if container is None:
        obj["shortcuts"] = {}; container = obj["shortcuts"]
    idx = next_index(container)
    entry = make_shortcut(name, exe, startdir, icon, launch_opts)
    container[idx] = entry
    if dry:
        info("DRY RUN: would add shortcut at index", idx)
        info(json.dumps(entry, indent=2)); return idx, entry
    backup(shortcuts_path); write_shortcuts(shortcuts_path, obj); return idx, entry

def set_compat_tool(config_vdf_path: Path, appid: int, tool_name: str, priority: int = DEFAULT_PRIORITY, dry=False):
    root = read_text_vdf(config_vdf_path) if config_vdf_path.exists() else {}
    store = root.setdefault("InstallConfigStore",{}).setdefault("Software",{}).setdefault("Valve",{}).setdefault("Steam",{})
    mapping = store.setdefault("CompatToolMapping",{})
    key = str(appid); mapping[key] = {"name": tool_name, "config": "", "Priority": str(priority)}
    if dry:
        info("DRY RUN: would write CompatToolMapping in", str(config_vdf_path)); info(f'{key}: {mapping[key]}'); return
    if config_vdf_path.exists(): backup(config_vdf_path)
    write_text_vdf(config_vdf_path, root)

def get_compat_tool(config_vdf_path: Path, appid: int):
    if not config_vdf_path.exists(): return None
    try:
        root = read_text_vdf(config_vdf_path)
        return (root.get("InstallConfigStore",{}).get("Software",{}).get("Valve",{}).get("Steam",{}).get("CompatToolMapping",{}).get(str(appid)))
    except Exception:
        return None

def scan_vanguard_args(timeout=120, poll=2):

    marker = SHIPPING_EXE_NAME
    deadline = time.time() + timeout
    info("Waiting to capture Vanguard runtime args (launch via the EVE Online launcher)…")
    while time.time() < deadline:
        for p in psutil.process_iter(attrs=("pid","cmdline")):
            try:
                cmd = p.info.get("cmdline") or []
                if not cmd: continue
                joined = " ".join(cmd)
                if marker in joined:
                    tail = joined.split(marker,1)[1].strip()
                    if tail.startswith('"') and tail.endswith('"'): tail = tail[1:-1]
                    info("Captured runtime args:", tail)
                    return tail
            except psutil.Error: pass
        time.sleep(poll)
    info("No args captured within timeout."); return ""

def load_saved_config():
    if not CONF_PATH.exists(): return {}
    try: return json.loads(CONF_PATH.read_text(encoding="utf-8"))
    except Exception: return {}

def save_config(d: dict):
    ensure_state_dirs()
    with CONF_PATH.open("w", encoding="utf-8") as fh: json.dump(d, fh, indent=2)

def print_status(saved: dict, steam_root: Path|None, profile_id: str|None, shortcuts_path: Path|None, config_vdf: Path|None, name: str):
    info("=== Status ===")
    info("Saved config path:", str(CONF_PATH))
    info("Log file:", str(LOG_PATH) if LOG_PATH else "(none)")
    if saved: info("Saved config keys:", ", ".join(sorted(saved.keys())))
    if steam_root: info("Steam root:", str(steam_root))
    if profile_id: info("Profile ID:", profile_id)
    if shortcuts_path and shortcuts_path.exists(): info("shortcuts.vdf:", str(shortcuts_path))
    if config_vdf and config_vdf.exists(): info("config.vdf:", str(config_vdf))
    try:
        if shortcuts_path and shortcuts_path.exists():
            obj = read_shortcuts(shortcuts_path)
            container = find_numeric_container(obj) or obj.get("shortcuts") or obj
            for k, ent in container.items():
                if isinstance(ent, dict) and ent.get("appname") == name:
                    appid = ent["appid"]; mapping = get_compat_tool(config_vdf, appid) if config_vdf else None
                    info(f"Detected shortcut index: {k}")
                    info(f"Shortcut AppID: {appid}")
                    info(f"LaunchOptions: {ent.get('LaunchOptions','')!r}")
                    info(f"Target exe: {ent.get('exe')}")
                    info(f"Proton mapping: {mapping if mapping else '(none)'}")
                    break
    except Exception as e: err("Status check failed:", str(e))


def run_injection(args):
    if is_steam_running(args.steam_root) and not args.dry_run and not args.force:
        err("Please EXIT Steam before running (or pass --force)."); sys.exit(1)

    saved = load_saved_config(); log("Loaded saved config:", json.dumps(saved, indent=2) if saved else "(none)")


    steam_root = Path(saved.get("steam_root")) if saved.get("steam_root") else None
    profile_id = saved.get("profile_id")
    shortcuts_path = Path(saved.get("shortcuts_vdf")) if saved.get("shortcuts_vdf") else None
    config_vdf = Path(saved.get("config_vdf")) if saved.get("config_vdf") else None

    if not (steam_root and shortcuts_path and config_vdf and steam_root.exists()):
        roots = find_userdata_roots(args.steam_root)
        if not roots:
            if args.no_prompt: err("Steam userdata not found and prompting disabled."); sys.exit(2)
            info("Steam userdata not found automatically.")
            guess = input("Enter Steam root (e.g. ~/.local/share/Steam): ").strip()
            if not guess: sys.exit(2)
            roots = find_userdata_roots(guess)
        steam_root, userdata = roots[0]
        profiles = find_profile_shortcuts(userdata)
        if not profiles: err("No Steam profiles found under:", str(userdata)); sys.exit(3)
        profile_id, shortcuts_path = profiles[0]
        config_vdf = steam_root / "config" / "config.vdf"
    info(f"Using Steam profile {profile_id}")

    compat_id = (args.compatdata_id or saved.get("compatdata_id") or DEFAULT_COMPATDATA_ID).strip()

    prefix = saved.get("prefix") or args.prefix
    eac_rel = saved.get("exe_rel")


    if args.exe:
        if not args.exe.replace("\\","/").endswith("/" + EAC_EXE_NAME) and not args.exe.endswith(EAC_EXE_NAME):
            err(f"--exe must point to {EAC_EXE_NAME} inside the prefix.")
            sys.exit(4)
        eac_rel = args.exe.replace("\\","/")


    if not validate_prefix_and_eac(prefix or "", eac_rel):
        prefix, eac_rel = auto_discover_eac(steam_root, compat_id)

    if not prefix or not eac_rel:
        if args.no_prompt:
            err("Could not auto-discover EAC path and prompting disabled."); sys.exit(5)
        info("Could not auto-discover EAC path.")
        prefix = input("Enter Vanguard Proton prefix (…/compatdata/<ID>/pfx): ").strip()
        eac_rel = input(f"Enter path to {EAC_EXE_NAME} relative to that prefix: ").strip()


    if not validate_prefix_and_eac(prefix, eac_rel):
        err("Resolved EAC exe not found.",
            "\n  PREFIX =", prefix,
            "\n  EXE_REL =", eac_rel,
            "\nTip: use --compatdata-id and/or --prefix to be explicit.")
        sys.exit(6)

    tail = ""
    if not args.dry_run:
        tail = scan_vanguard_args(timeout=args.timeout)

    info("Waiting for Steam to exit before continuing")
    while is_steam_running(args.steam_root) and not args.dry_run and not args.force:
        time.sleep(1)


    eac_abs_path = (Path(prefix).expanduser() / eac_rel).resolve()
    eac_abs = str(eac_abs_path); startdir = str(eac_abs_path.parent)

    idx, entry = inject_shortcut(shortcuts_path, args.name, eac_abs, startdir, args.icon, "", args.dry_run)
    info(f"Shortcut injected (index {idx}) at {shortcuts_path}")
    info(f"Target exe (EAC): {eac_abs}")


    if tail:
        obj = read_shortcuts(shortcuts_path)
        container = find_numeric_container(obj) or obj.get("shortcuts") or obj
        if idx in container:
            container[idx]["LaunchOptions"] = tail
            backup(shortcuts_path); write_shortcuts(shortcuts_path, obj)
            info("Patched LaunchOptions =", tail)
    else:
        info("Proceeding without LaunchOptions (none captured).")


    appid = entry["appid"] + (1<<32)
    info(f"Computed AppID: {appid}")
    set_compat_tool(config_vdf, appid, args.proton, args.priority, args.dry_run)
    info(f"Set CompatToolMapping for AppID {appid} -> '{args.proton}'")


    state = {
        "steam_root": str(steam_root),
        "profile_id": profile_id,
        "shortcuts_vdf": str(shortcuts_path),
        "config_vdf": str(config_vdf),
        "prefix": str(prefix),
        "exe_rel": eac_rel,
        "shortcut_name": args.name,
        "appid": appid,
        "proton_tool": args.proton,
        "priority": args.priority,
        "compatdata_id": compat_id,
        "target": "eac",
    }
    save_config(state); info(f"Saved config -> {CONF_PATH}")
    info("Done. Start Steam and launch the new shortcut.")

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

    ap = argparse.ArgumentParser(description=f"{APP_NAME}: inject Steam shortcut to EAC, capture args, set Proton.")
    ap.add_argument("--steam-root", help="Steam root (e.g. ~/.local/share/Steam)")
    ap.add_argument("--compatdata-id", help=f"Compatdata AppID folder to search (default {DEFAULT_COMPATDATA_ID})")
    ap.add_argument("--prefix", help="Proton prefix root (…/compatdata/<ID>/pfx)")
    ap.add_argument("--exe", help=f"Path INSIDE the prefix to {EAC_EXE_NAME} (overrides auto-discovery; must be EAC)")
    ap.add_argument("--name", default=DEFAULT_SHORTCUT_NAME, help="Shortcut name")
    ap.add_argument("--icon", default="", help="Icon path")
    ap.add_argument("--proton", default=DEFAULT_PROTON, help="Steam Play tool to use")
    ap.add_argument("--priority", type=int, default=DEFAULT_PRIORITY, help="Compat tool priority")
    ap.add_argument("--timeout", type=int, default=120, help="Seconds to wait when capturing Shipping args")
    ap.add_argument("--dry-run", action="store_true", help="Preview only; no writes")
    ap.add_argument("--no-prompt", action="store_true", help="Disable prompts on discovery failure")
    ap.add_argument("--status", action="store_true", help="Show status and exit")
    ap.add_argument("--force", action="store_true", help="Bypass Steam-running check")
    ap.add_argument("--debug", action="store_true", help="Verbose console output")
    args = ap.parse_args()
    DEBUG = args.debug

    info(DISCLAIMER)
    info(f"{APP_NAME} starting…")
    info(f"Log file: {LOG_PATH}")

    try:
        if args.status:
            run_status(); return
        run_injection(args)
    except KeyboardInterrupt:
        err("Interrupted by user.")
    except Exception as e:
        err("Unhandled error:", str(e))
        _write_log_line(traceback.format_exc())
        err("Traceback written to log file:", str(LOG_PATH))
        sys.exit(99)

if __name__ == "__main__":
    main()
