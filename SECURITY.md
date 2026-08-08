# QuickDrop Security

QuickDrop v2 is designed for transfers between devices on a **trusted private/local network**.

## Security model

QuickDrop v2:

- rejects clients whose source address is not recognized as private/local;
- creates a fresh temporary 6-digit PIN for a new sharing session;
- issues separate random authenticated session credentials after successful authentication;
- rate-limits repeated incorrect PIN attempts;
- exposes only files the PC user explicitly added to the current share list;
- sanitizes incoming filenames and avoids silent overwrites;
- enforces PC-selected upload permissions and file-size limits on the server;
- checks available receive-drive space before accepting large uploads;
- can disable downloads, phone uploads, Quick Text, or trusted-device access independently;
- stores only a hash/digest of a trusted-device secret on the PC;
- allows all remembered devices to be revoked from QuickDrop Settings;
- uses restrictive browser security headers and does not load third-party web resources in the phone UI.

## Important transport limitation

QuickDrop v2 currently uses **HTTP on the local network** so phones can connect without installing a certificate or native app. The connection is therefore not end-to-end encrypted at the transport layer.

Use QuickDrop only on networks you trust. Do **not** use it on public/untrusted Wi-Fi for sensitive or confidential files.

## Trusted devices

A remembered phone keeps a random device secret in that browser's local storage. The PC stores a digest instead of the raw secret. Anyone with control of that browser profile may be able to use its remembered QuickDrop credential until you revoke trusted devices.

If a phone is lost, shared, reset, or no longer trusted, use **Settings → Forget all trusted devices**.

## Windows Firewall

QuickDrop needs inbound access on a dynamically selected local TCP port while a sharing session is active. If Windows Firewall prompts, allow QuickDrop on **Private networks** only unless you explicitly understand and accept the risk.

## Reporting security issues

Do not publish sensitive exploit details in a public issue. Contact **impreseo** through the official QuickDrop GitHub profile/repository to coordinate a security report.
