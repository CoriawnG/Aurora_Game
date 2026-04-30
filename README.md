# Aurora

Aurora is a choice-driven policy simulation game with a Pygame front end and bundled art, debate scripts, and citations.

## Player Release

The project is now set up to produce a clean Windows zip release for players:

- `Aurora.exe`
- `README.txt`
- `LICENSE.txt`
- `THIRD_PARTY_NOTICES.txt`
- `PressStart2P-OFL.txt`

Ending summaries created during play are written to:

```text
%LOCALAPPDATA%\Aurora\endings
```

That keeps player data out of the packaged app bundle, which is important for zipped and one-file builds.

## Run From Source

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Run the game:

```bash
python aurora_pygame.py
```

Optional audio files:

- `assets/audio/music.ogg`
- `assets/sfx/click.wav`

## Build The Windows Zip

Use the included PowerShell build script from the repo root:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\build_windows_release.ps1
```

The script:

- builds `Aurora.exe` with PyInstaller
- creates a clean versioned release folder under `release\`
- copies the player-facing docs and license files
- extracts the bundled font license text
- produces `release\Aurora-<version>-Windows.zip`

## Notes

- `build\web\` contains earlier web/mobile build artifacts and is not the recommended player handoff for Windows.
- `aurora_gui.py` remains available for the original Tk-based implementation, but `aurora_pygame.py` is the packaged player build target.
