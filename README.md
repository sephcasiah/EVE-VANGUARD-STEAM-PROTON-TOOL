# EVEVANGUARD_Shortcut_Inst

**EVEVANGUARD_Shortcut_Inst** automates adding **EVE Vanguard** as a Non-Steam game on Linux, with Proton enabled and Vanguard’s runtime arguments automatically captured.  

It eliminates the need to manually edit Steam’s `shortcuts.vdf`, copy arguments from `ps aux`, or set Proton compatibility yourself. After running the tool and restarting Steam, EVE Vanguard will appear in your Steam library, ready to launch.

---

## Disclaimer

- This tool does **not** modify CCP’s EVE Vanguard client, launcher, or any CCP software.  
- All rights, trademarks, and copyrights for EVE and EVE Vanguard belong to **CCP hf**.  
- This tool only edits your **local Steam configuration files** (`shortcuts.vdf`, `config.vdf`).  
- Use at your own risk; results may vary.  
- For issues, contact the maintainer. Do **not** contact CCP for support.

---

## Features

- Auto-detects Steam installation and Vanguard Proton prefix.  
- Prompts for paths **only if automatic discovery fails**.  
- Injects a Non-Steam shortcut for **EVE Vanguard** into your Steam library.  
- Auto-captures Vanguard’s runtime arguments the first time you launch it.  
- Sets the Proton version for Vanguard in Steam (`CompatToolMapping`).  
- Backs up `shortcuts.vdf` and `config.vdf` before changes.  
- Saves a config file for faster re-runs.  
- Writes a detailed log file each run.  
- Includes a `--status` mode to check the current shortcut and Proton mapping.  


## Requirements

- Linux with Steam installed  
- Python 3.7+  
- Python dependencies:
  ```
  python3 -m pip install --user vdf psutil
  ```
---

## Quickstart

1. Close Steam.
2. Run the installer:

   ```
   python3 EVEVANGUARD_Shortcut_Inst.py
   ```
3. Start **EVE Vanguard** once via the EVE Online launcher.

   * The tool will capture Vanguard’s runtime arguments automatically.
4. Restart Steam.

   * You’ll see **EVE Vanguard** in your library, ready to run with Proton.

---

## Options

```bash
python3 EVEVANGUARD_Shortcut_Inst.py [options]
```

* `--steam-root PATH` : Override Steam root directory.
* `--prefix PATH` : Override Proton prefix path.
* `--exe PATH` : Override Vanguard exe path relative to prefix.
* `--name NAME` : Shortcut name (default: "EVE Vanguard").
* `--proton TOOL` : Proton version to use (default: `proton_experimental`).
* `--priority N` : Proton priority (default: 250).
* `--timeout SECS` : Seconds to wait for Vanguard runtime args (default: 120).
* `--dry-run` : Preview changes without writing files.
* `--no-prompt` : Disable prompts; fail if discovery incomplete.
* `--status` : Show current shortcut, AppID, and Proton mapping without making changes.
* `--debug` : Verbose console output (in addition to log file).

---

## Logs & Config

* Config file:
  `~/.config/EVEVANGUARD_Shortcut_Inst/config.json`

* Logs:
  `~/.config/EVEVANGUARD_Shortcut_Inst/logs/run-*.log`

Send the latest log file to the maintainer if you encounter problems.

---

## Examples

Normal use case:

```
python3 EVEVANGUARD_Shortcut_Inst.py
```

Or if needed/tinkering

```
python3 EVEVANGUARD_Shortcut_Inst.py --proton "Proton 10" --debug
```

This will:

* Inject the EVE Vanguard shortcut
* Capture runtime arguments
* Set Proton 10 as the compatibility tool
* Print debug info to the console and save it in a log file
