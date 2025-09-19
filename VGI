#!/usr/bin/env python3
# EVE Vanguard: capture Shipping.exe args -> save to a Non-Steam/Proton shortcut (Linux)
import os, sys, time, struct, subprocess, argparse
from pathlib import Path


DEFAULT_SHORTCUT_NAME = "EVE Vanguard"
# Target of the Non-Steam shortcut (Windows path seen by Proton/Wine)
WIN_TARGET = r'C:\Program Files\CCP\EVE\Eve-vanguard\live\WindowsClient\EVEVanguardClient-Win64-Shipping.exe'
PROTON_MAPPING = "proton_experimental"  # You can still override in Steam → Properties → Compatibility
PROC_NAME = "EVEVanguardClient-Win64-Shipping.exe"
SCAN_INTERVAL = 1.0
TIMEOUT_SEC = 1800

def find_steam_root() -> Path:
    cands = [
        Path.home() / ".local/share/Steam",
        Path.home() / ".steam/steam",
        Path.home() / ".var/app/com.valvesoftware.Steam/.local/share/Steam",  # Flatpak
    ]
    for p in cands:
        if (p / "steamapps").is_dir():
            return p
    raise FileNotFoundError("Could not find Steam root in standard locations.")

def list_profiles(steam_root: Path):
    u = steam_root / "userdata"
    return sorted([d for d in u.iterdir() if d.is_dir() and d.name.isdigit()], key=lambda p: p.name)

def pick_profile(steam_root: Path, force_id: str | None):
    profs = list_profiles(steam_root)
    if not profs:
        raise RuntimeError("No Steam profiles under userdata/")
    if force_id:
        m = [p for p in profs if p.name == force_id]
        if not m: raise RuntimeError(f"Profile {force_id} not found.")
        print(f"[+] Using Steam profile {force_id}")
        return m[0]
    if len(profs) == 1:
        print(f"[+] Using Steam profile {profs[0].name}")
        return profs[0]
    print("Multiple Steam profiles found:\n")
    for i,p in enumerate(profs,1): print(f"  [{i}] {p.name}")
    while True:
        sel = input("\nSelect a profile number: ").strip()
        if sel.isdigit() and 1 <= int(sel) <= len(profs):
            pick = profs[int(sel)-1]
            print(f"[+] Using Steam profile {pick.name}")
            return pick
        print("Invalid selection.")

# ---- Steam running guard ----
def is_steam_running() -> bool:
    for pid in filter(str.isdigit, os.listdir("/proc")):
        try:
            with open(f"/proc/{pid}/cmdline","rb") as f:
                d = f.read().lower()
            if b"/steam" in d or b"steamwebhelper" in d or b"steam" in d:
                return True
        except Exception:
            pass
    return False

def ensure_steam_closed():
    if not is_steam_running(): return
    print("[!] Steam seems to be running. Please close Steam; waiting…")
    while is_steam_running(): time.sleep(1.0)
    print("[+] Detected Steam exit.")

def read_cmdline(pid: str) -> str:
    with open(f"/proc/{pid}/cmdline","rb") as f:
        data = f.read()
    return data.replace(b"\x00", b" ").decode("utf-8", errors="ignore")

def capture_tail(timeout=TIMEOUT_SEC) -> str:
    target = PROC_NAME.lower()
    print(f"[+] Waiting for {PROC_NAME} (timeout {timeout}s)…")
    t0 = time.time()
    while time.time() - t0 < timeout:
        for pid in filter(str.isdigit, os.listdir("/proc")):
            try:
                cmd = read_cmdline(pid)
            except Exception:
                continue
            low = cmd.lower()
            i = low.find(target)
            if i != -1:
                j = low.find(".exe", i)
                if j != -1:
                    j += 4
                    tail = cmd[j:].strip()
                    print(f"[+] Captured args tail: {tail!r}")
                    return tail
        time.sleep(SCAN_INTERVAL)
    raise TimeoutError("Timed out waiting for Shipping.exe")


TYPE_END, TYPE_STRING, TYPE_INT32, TYPE_ARRAY = 0x08, 0x01, 0x02, 0x00

def _rcs(f):
    b = bytearray()
    while True:
        c = f.read(1)
        if not c: raise EOFError("EOF in cstring")
        if c == b"\x00": return b.decode("utf-8", "replace")
        b.extend(c)

def _wcs(f, s: str): f.write(s.encode("utf-8")+b"\x00")
def _ri(f): return struct.unpack("<i", f.read(4))[0]
def _wi(f, i): f.write(struct.pack("<i", int(i)))

def _read_node(f):
    node = {}
    while True:
        t = f.read(1)
        if not t: raise EOFError("EOF reading node")
        t = t[0]
        if t == TYPE_END: return node
        key = _rcs(f)
        if t == TYPE_STRING: node[key] = ("string", _rcs(f))
        elif t == TYPE_INT32: node[key] = ("int32", _ri(f))
        elif t == TYPE_ARRAY: node[key] = ("array", _read_node(f))
        else: raise ValueError(f"Unknown type: {t}")

def _write_node(f, node: dict):
    for k,(kind,val) in node.items():
        if kind=="string":
            f.write(bytes([TYPE_STRING])); _wcs(f,k); _wcs(f,val)
        elif kind=="int32":
            f.write(bytes([TYPE_INT32])); _wcs(f,k); _wi(f,val)
        elif kind=="array":
            f.write(bytes([TYPE_ARRAY])); _wcs(f,k); _write_node(f,val)
        else: raise ValueError(f"Bad kind: {kind}")
    f.write(bytes([TYPE_END]))

def read_shortcuts(path: Path):
    if not path.exists(): return {"shortcuts": ("array", {})}
    with open(path,"rb") as f: top = _read_node(f)
    return top

def write_shortcuts(path: Path, top: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".vdf.tmp")
    with open(tmp,"wb") as f: _write_node(f, top)
    if path.exists(): path.replace(path.with_suffix(".vdf.bak"))
    tmp.replace(path)

def ensure_shortcut(top: dict, name: str, exe: str, launch_options: str):
    if "shortcuts" not in top: top["shortcuts"] = ("array", {})
    arr = top["shortcuts"][1]
    target_idx = None
    for k,v in arr.items():
        if not k.isdigit(): continue
        entry = v[1]
        if entry.get("appname",("string",""))[1] == name:
            target_idx = k; break
    if target_idx is None:
        next_idx = max([int(i) for i in arr.keys() if i.isdigit()] or [-1]) + 1
        target_idx = str(next_idx)
        arr[target_idx] = ("array", {})
    entry = arr[target_idx][1]
    entry["appname"] = ("string", name)
    entry["exe"] = ("string", exe)              # Windows path is fine; Proton handles it
    entry["StartDir"] = ("string", "")
    entry["icon"] = ("string", "")
    entry["ShortcutPath"] = ("string", "")
    entry["LaunchOptions"] = ("string", launch_options)
    entry["IsHidden"] = ("int32", 0)
    entry["AllowDesktopConfig"] = ("int32", 1)
    entry["AllowOverlay"] = ("int32", 1)
    entry["OpenVR"] = ("int32", 0)
    entry["Devkit"] = ("int32", 0)
    entry["DevkitGameID"] = ("string", "")
    entry["LastPlayTime"] = ("int32", 0)
    entry["FlatpakAppID"] = ("string", "")
    # tags
    entry["tags"] = ("array", {"0": ("string","Games"), "1": ("string","Vanguard")})

def set_proton_mapping(config_vdf: Path, shortcut_name: str, tool: str):
    txt = ""
    if config_vdf.exists():
        try: txt = config_vdf.read_text(encoding="utf-8", errors="ignore")
        except Exception: pass
    block = '"CompatToolMapping"'
    if block not in txt:
        txt = txt.rstrip() + f'\n{block}\n{{\n}}\n'
    lines, out, inside, replaced = txt.splitlines(), [], False, False
    for ln in lines:
        if not inside and ln.strip()==block:
            inside="open_pending"; out.append(ln); continue
        if inside=="open_pending":
            out.append(ln)
            if ln.strip()=="{": inside=True
            continue
        if inside is True:
            if ln.strip()=="}":
                if not replaced:
                    out.append(f'\t"{shortcut_name}"\t"{tool}"'); replaced=True
                out.append(ln); inside=False; continue
            if ln.strip().startswith(f'"{shortcut_name}"'):
                out.append(f'\t"{shortcut_name}"\t"{tool}"'); replaced=True; continue
        out.append(ln)
    new = "\n".join(out)
    config_vdf.parent.mkdir(parents=True, exist_ok=True)
    config_vdf.write_text(new, encoding="utf-8")

def parse_args():
    p = argparse.ArgumentParser(description="Capture Vanguard args and save to a Non-Steam/Proton shortcut.")
    p.add_argument("--name", default=DEFAULT_SHORTCUT_NAME, help="Shortcut name to update/create.")
    p.add_argument("--profile", help="Steam profile ID (e.g., 162331869). Prompt if omitted and multiple exist.")
    p.add_argument("--timeout", type=int, default=TIMEOUT_SEC, help="Seconds to wait for Shipping.exe.")
    p.add_argument("--no-proton-map", action="store_true", help="Skip writing CompatToolMapping.")
    return p.parse_args()

def main():
    args = parse_args()
    steam_root = find_steam_root()
    profile_dir = pick_profile(steam_root, args.profile)

    # 1) Wait for Shipping.exe and capture args tail
    tail = capture_tail(timeout=args.timeout)  # blocks until found or timeout

    # 2) Ensure Steam is closed before writing config
    ensure_steam_closed()

    # 3) Update/Create Non-Steam shortcut with captured args
    shortcuts = profile_dir / "config" / "shortcuts.vdf"
    top = read_shortcuts(shortcuts)
    ensure_shortcut(top, name=args.name, exe=WIN_TARGET, launch_options=tail)
    write_shortcuts(shortcuts, top)
    print(f"[+] Wrote Launch Options to shortcut “{args.name}”.")
    print(f"    File: {shortcuts}")

    # 4) (Optional) Force Proton for this shortcut
    if not args.no_proton_map:
        cfg = profile_dir / "config" / "config.vdf"
        set_proton_mapping(cfg, args.name, PROTON_MAPPING)
        print(f"[+] Ensured Proton mapping in {cfg}")

    print("\nDone. Start Steam → find your Non-Steam shortcut → launch Vanguard.\n"
          "If you don’t see the shortcut, restart Steam.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted."); sys.exit(130)
    except Exception as e:
        print(f"ERROR: {e}"); sys.exit(1)
