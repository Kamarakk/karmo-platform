# KARMO Access Registry Change Log

## 2026-09-11
- Created structured Access & Connection Registry framework.
- Recorded verified KARMO-AI01 LAN address, KVE02 Tailscale address, KARMO-DEV01/office Tailscale addresses, SSH identity reference, and Remote Desktop Commander as an alternate access method.
- Preserved the existing KVE02 jump-host route as a verified fallback.
- Added a planned direct KARMO-AI01 Tailscale path with status `NEEDS_VERIFICATION`; do not mark it active until install/enrollment and direct SSH verification complete.
- Added recovery classification separating routing, transport, SSH, authentication, authorization, privilege, and application-layer failures.

Do not record secret values in this log.