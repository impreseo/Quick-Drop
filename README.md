# QuickDrop v2

**QuickDrop** is a private local-network transfer utility for moving files, folders, and text between a Windows PC and a phone without a cloud account or phone app.

Built and owned by **impreseo**.

## Final v2 feature set

- PC → phone file downloads
- Phone → PC uploads with live progress
- Multiple-file phone uploads
- Drag-and-drop on the phone browser where supported
- Drag-and-drop into the Windows app when the bundled DnD component is available
- Folder sharing as temporary ZIP archives
- **Download All** bundle for multiple shared items
- Quick Text for links, notes, code, addresses, and clipboard snippets
- Friendly connected-device names in transfer history
- Remember/trust a phone for faster reconnects
- Revoke all trusted devices from Windows Settings
- Fresh 6-digit PIN for new sessions
- Random per-client authenticated session cookies
- PIN brute-force throttling
- 15 / 30 / 60 / 120-minute session lifetime
- PC-controlled permissions for downloads, uploads, and Quick Text
- Configurable 100 MB to 10 GB per-file upload limit
- Server-side upload limit enforcement
- Free-disk-space check before accepting large uploads
- Private/local-network client restriction
- Collision-safe received filenames instead of overwriting files
- Received files default to `Downloads\QuickDrop`
- Configurable receive folder
- Local transfer history (latest 500 events)
- Resume-capable HTTP range downloads where the client/browser supports ranges
- Responsive dark phone UI
- Dark Windows desktop UI
- Local troubleshooting log
- Report Bug, Request Feature, Feedback, and Update actions
- GitHub / Instagram / LinkedIn / Discord contact links for `impreseo`
- No QuickDrop account
- No ads or analytics SDK
- No QuickDrop cloud upload service

## Normal installation

Public releases should be shared as:

```text
QuickDrop-Setup-2.0.0.exe
```

Installation is designed to be straightforward:

```text
Download setup
   ↓
Double-click QuickDrop-Setup-2.0.0.exe
   ↓
Accept the QuickDrop Proprietary Freeware License
   ↓
Optional desktop shortcut
   ↓
Install
   ↓
Launch QuickDrop
```

The setup is per-user by default and normally does not require administrator rights. It creates a Start Menu entry, an optional desktop shortcut, a standard Windows uninstall entry, and can launch QuickDrop after setup.

The installed app bundles Python and its required runtime libraries. End users do **not** need Python, pip, or a terminal.

Windows Firewall may ask whether QuickDrop may communicate on **Private networks**. Private-network access is required for phone-to-PC communication. Do not enable QuickDrop on untrusted public networks.

## Using QuickDrop

1. Open QuickDrop on the PC.
2. Make sure the PC and phone are connected to the same trusted Wi-Fi/LAN.
3. Add files or folders on **Send**.
4. Scan the QR code shown on **Home**.
5. Name the phone and enter the temporary 6-digit PIN.
6. Optionally choose **Remember this device**.
7. Download files, upload files, or use Quick Text according to the permissions enabled on the PC.
8. Stop the session when finished, or let it expire automatically.

## Privacy controls

The PC owner controls whether a connected phone may:

- download shared items;
- upload files;
- use Quick Text;
- be remembered as a trusted device;
- upload files above a chosen size limit.

Changing these controls while a session is active refreshes the session.

## Trusted devices

When a phone is remembered, QuickDrop stores a random device credential in the phone browser and stores only a cryptographic digest of that secret on the PC. Trusted devices can be revoked from QuickDrop Settings at any time.

Remembered-device access should only be enabled for devices you control.

## Repository layout

```text
QuickDrop/
├─ src/quickdrop/
│  ├─ core/          models, storage, security, trusted devices
│  ├─ services/      HTTP server, transfers, network discovery
│  ├─ ui/            Windows desktop interface
│  ├─ web/           responsive phone browser interface
│  └─ assets/        application icon
├─ tests/             core and end-to-end server tests
├─ installer/         Inno Setup installer + EXE metadata
├─ scripts/           single Windows release build script
├─ .github/           issue forms + Windows CI/release workflow
├─ LICENSE
├─ THIRD_PARTY_NOTICES.md
├─ SECURITY.md
└─ README.md
```

The repository intentionally excludes generated build folders, release binaries, duplicate build systems, placeholder screenshots, and unused future-feature stubs.

## Run from source

Python 3.11+:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m quickdrop
```

Tests:

```powershell
python -m unittest discover -s tests -v
```

## Build the Windows installer

Install Python 3.11+ and Inno Setup 6 on the Windows build machine, then run:

```bat
scripts\build.bat
```

The build script creates an isolated environment, installs only the required build dependencies, runs the tests, builds the bundled Windows application with PyInstaller, and builds the Inno Setup installer.

Expected output:

```text
release\QuickDrop-Setup-2.0.0.exe
```

The included GitHub Actions Windows workflow can also build the installer and attach it to tagged releases.

## Feedback, Suggestions & Other Apps

We welcome all feedback, feature requests, suggestions, bug reports, and community ideas!

- **Report Bugs**: [GitHub Bug Report](https://github.com/impreseo/Quick-Drop/issues/new?template=bug.yml)
- **Request Features / Give Suggestions**: [GitHub Feature & Suggestion Request](https://github.com/impreseo/Quick-Drop/issues/new?template=feature.yml)
- **General Feedback & Discussions**: [GitHub Issues & Feedback](https://github.com/impreseo/Quick-Drop/issues)
- **Latest Updates & Releases**: [QuickDrop GitHub Releases](https://github.com/impreseo/Quick-Drop/releases)
- **Discover Other Apps & Projects**: Visit our official GitHub profile at [github.com/impreseo](https://github.com/impreseo) to check out our other applications and projects.

### Connect with impreseo

- **GitHub**: [@impreseo](https://github.com/impreseo)
- **Instagram**: [@impreseo](https://instagram.com/impreseo)
- **LinkedIn**: [impreseo](https://www.linkedin.com/in/impreseo/)
- **Discord**: `@impreseo`

Feel free to open an issue, submit suggestions, or reach out on any of our official accounts given above!

## License

QuickDrop is **proprietary freeware / source-visible software**, not MIT-licensed open source.

You may use official unmodified QuickDrop releases under the terms in [`LICENSE`](LICENSE). Modification, rebranding, source reuse, modified redistribution, resale, or derivative versions require prior written permission from **impreseo**.

Third-party components bundled with QuickDrop remain covered by their own licenses. See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
