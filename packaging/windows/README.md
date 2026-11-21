# Vaderland 33 Windows preview

The x64 installer bundles Python, its runtime dependencies and one exact VTX revision. Install it for the current Windows user, then open the build from **Start → VTX**. It opens the local cockpit in an Edge app window when Edge is available and uses the default browser otherwise. Keep the accompanying simulator console open during play.

The simulator binds to loopback port 8776. This preview keeps each build's flight records and harbour saves under `%LOCALAPPDATA%\VTX\installed-v33\<build>`. Uninstalling removes the program and leaves those saves in place. Existing VTX checkouts and their saves have their own locations.

## Build

Run this from a Windows x64 checkout with Python 3.14.3, Git and uv available. Pass the official [Python 3.14.3 Windows x64 embeddable ZIP](https://www.python.org/downloads/release/python-3143/) and the executable from the [NSIS compiler ZIP](https://sourceforge.net/projects/nsis/files/NSIS%203/3.13/). The script verifies the Python archive, installs packages from the hash-pinned Windows lock and exports game files from the selected commit.

```powershell
python scripts/build_windows_installer.py --compiler C:\tools\nsis\makensis.exe --python-archive C:\tools\python-3.14.3-embed-amd64.zip --output-dir C:\builds\vaderland-preview
```

The build checks the bundled runtime and writes an installer and SHA-256 receipt to the new output directory. This is a local, unsigned preview installer.
