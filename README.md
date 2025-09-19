# EVE Vanguard – Steam Shortcut Installer

Creates a Steam **Non-Steam** shortcut that launches EVE Vanguard via **Easy Anti-Cheat (EAC)** under Proton.  
It auto-discovers the correct Proton prefix across **all Steam libraries**, writes an **absolute** target path, optionally captures runtime args from the official launcher, and sets a Proton mapping for the computed Non-Steam AppID.

> **Disclaimer:** This tool does **not** modify CCP software. All trademarks and copyrights for EVE / EVE Vanguard belong to CCP hf.  
> It only edits your local Steam configuration files (`shortcuts.vdf`, `config.vdf`). Use at your own risk; **do not** contact CCP for support.

---

## What it does

- Adds a Non-Steam game entry (default name: **“EVE Vanguard”**).
- Shortcut **always** targets `start_protected_game.exe` (EAC bootstrap).
- Uses an **absolute path** into your Proton prefix (fixes no-launch/instant-crash issues).
- Searches **every** Steam Library (`libraryfolders.vdf`) for `steamapps/compatdata/<ID>/pfx`.
- **captures Vanguard runtime args** from the official launcher and writes them to `LaunchOptions`.
- Sets a **Steam Play (Proton)** mapping for the Non-Steam AppID.

---

## Requirements

- **Linux** with Steam + Proton.
- **Python 3.10+** (uses `|` type hints).
- Python packages:
  ```bash
  python3 -m pip install --user vdf psutil
  ```

---

## Quickstart

1. **Quit Steam** completely.
2. Run the installer:

   ```
   python3 EVEVANGUARD_Shorcut_Inst.py --debug
   ```
3. When it prints **“Waiting to capture Vanguard runtime args …”**, launch Vanguard once **from the official EVE Online launcher**.
   The script will detect the Shipping process and capture the tail args (optional).
4. The script finishes and prints the log path.
   **Start Steam** and launch the new **EVE Vanguard** shortcut.

If your game is on an external drive, the script should auto-find the correct prefix (e.g. `/mnt/.../SteamLibrary/steamapps/compatdata/8500/pfx`).
You can also pass the prefix explicitly (see examples).

---

## Usage

```
python3 EVEVANGUARD_Shorcut_Inst.py [OPTIONS]
```

**Options:**

* `--steam-root <PATH>` – Force Steam root (e.g. `~/.local/share/Steam`).
* `--compatdata-id <ID>` – Compatdata folder to search (default: `8500`).
* `--prefix <PATH>` – Proton prefix root (must end with `/pfx`), e.g.
  `/path/to/SteamLibrary/steamapps/compatdata/8500/pfx`
* `--exe <RELATIVE_PATH>` – Path **inside** the prefix to `start_protected_game.exe`
  (overrides discovery; must point to EAC).
* `--name <STR>` – Shortcut name (default: `EVE Vanguard`).
* `--icon <PATH>` – Optional icon.
* `--proton <TOOL>` – Steam Play tool (default: `proton_experimental`).
* `--priority <INT>` – Proton mapping priority (default: `250`).
* `--timeout <SECS>` – Seconds to wait while capturing runtime args (default: `120`).
* `--dry-run` – Preview changes; don’t write files.
* `--status` – Print current shortcut/mapping info and exit.
* `--force` – Proceed even if Steam is still running.
* `--debug` – Verbose console logging (also saves to log file).

---

## Examples

**Auto-discover everything (recommended):**

```
python3 EVEVANGUARD_Shorcut_Inst.py --debug
```

**Explicit external library + EAC path:**

```
python3 EVEVANGUARD_Shorcut_Inst.py --debug \
  --compatdata-id 8500 \
  --prefix "/mnt/drive/SteamLibrary/steamapps/compatdata/8500/pfx" \
  --exe "drive_c/CCP/EVE/eve-vanguard/live/WindowsClient/start_protected_game.exe"
```

**Just check what’s installed/mapped:**

```
python3 EVEVANGUARD_Shorcut_Inst.py --status
```

**Preview without writing:**

```
python3 EVEVANGUARD_Shorcut_Inst.py --dry-run --debug
```

---

## What gets written

* **`shortcuts.vdf`** (per-profile): adds/updates the Non-Steam entry with:

  * `exe`: absolute path to `start_protected_game.exe` inside your Proton prefix
  * `StartDir`: directory of the exe
  * `LaunchOptions`: captured Vanguard args (if any)
* **`config.vdf`** (global): adds a `CompatToolMapping` for the Non-Steam AppID.

Backups are created next to the original file, e.g. `shortcuts.vdf.bak.<timestamp>`.

**State & logs:**

* Config: `~/.config/EVEVANGUARD_Shortcut_Inst/config.json`
* Logs: `~/.config/EVEVANGUARD_Shortcut_Inst/logs/run-YYYYMMDD-HHMMSS.log`

---

## Troubleshooting

**Game doesn’t launch / shortcut points to wrong place**

* Run with `--debug`, then `--status` and check:

  * `Target exe` path points into `…/compatdata/<ID>/pfx/drive_c/…/start_protected_game.exe`
  * `LaunchOptions` contains captured args (optional)
  * Proton mapping exists for the shown **Non-Steam AppID**
* If the prefix is on another drive, pass it explicitly with `--prefix` (and `--compatdata-id` if needed).

**Steam was still running**

* Fully exit Steam or run the script with `--force`.

**Proton issues**

* In Steam, right-click shortcut → **Properties → Compatibility** and try:

  * Proton 9 (stable), then Proton Experimental, or Proton-GE (if installed).

**Get a Proton log**

* In Steam Properties → **Launch Options**, temporarily set:

  ```
  PROTON_LOG=1 %command% <captured-args-here>
  ```

  (Keep the captured args after `%command%`.)
* Launch the shortcut; check `~/steam-*.log`.

If problems persist, include:

* Script log (`~/.config/EVEVANGUARD_Shortcut_Inst/logs/run-*.log`)
* Output of `python3 EVEVANGUARD_Shorcut_Inst.py --status`
* Proton version used and any `~/steam-*.log`

---

## Uninstall / Revert

* Delete the Non-Steam shortcut from Steam’s UI.
* (Optional) Remove the specific `CompatToolMapping` entry for the Non-Steam AppID from `config.vdf`.
* You can also delete `~/.config/EVEVANGUARD_Shortcut_Inst/` to clear saved config/logs.

---

## Security & Privacy

* No network calls. Will not trip Anti-Cheat!
* Only touches local Steam config files and the tool’s own config/logs.
* Captured runtime args are stored in the shortcut’s `LaunchOptions` and logs.

## Credit

Big props to the handful of testers and to Prommah for being such a big help!
