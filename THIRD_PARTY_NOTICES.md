# Third-Party Notices

QuickDrop itself is **proprietary freeware** and is licensed under the
`QuickDrop Proprietary Freeware License v1.0` in `LICENSE`.

The Windows application may bundle third-party software. Those components keep
their own licenses; their licenses do **not** make QuickDrop itself open-source.

## Runtime components

### Pillow
Used to render the desktop QR image. Pillow is distributed under the
MIT-CMU license. See the Pillow project for the complete upstream license and
notices, including notices for third-party libraries that may be present in
Pillow wheels.

### python-qrcode
Used to generate QR codes. python-qrcode is distributed under a BSD license.
See the python-qrcode project for the complete upstream license text.

### tkinterdnd2 / tkDnD
Used for optional native drag-and-drop support. The package wraps the tkDnD Tcl/Tk
extension and includes upstream components with their own notices. See the
upstream tkinterdnd2 and tkDnD distributions for the complete applicable terms.

### Python / Tcl / Tk
The packaged Windows application includes Python runtime components and Tcl/Tk
runtime files. These remain subject to their upstream licenses.

## Build component

### PyInstaller
PyInstaller is used to create the Windows executable bundle. PyInstaller's
license contains an exception intended to allow distribution of applications
built with it. See PyInstaller's official license documentation for complete
terms.

## Source of truth

For every third-party component, the license shipped by the exact bundled
version is the source of truth. A release builder should retain required
notices from the bundled wheels/distributions when preparing public releases.
