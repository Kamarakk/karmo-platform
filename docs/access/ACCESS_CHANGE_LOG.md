# KARMO Access Registry Change Log

## 2026-09-11
- Created structured Access & Connection Registry framework.
- Recorded verified KARMO-AI01 LAN address, KVE02 Tailscale address, KARMO-DEV01/office Tailscale addresses, SSH identity reference, and Remote Desktop Commander as an alternate access method.
- Preserved the existing KVE02 jump-host route as a verified fallback.
- Enrolled KARMO-AI01 directly into the existing tailnet at `100.75.239.44` using the official Tailscale client with production DNS acceptance disabled.
- Kept normal OpenSSH/key authentication; Tailscale SSH, subnet routing, and exit-node behavior were not enabled.
- Promoted the direct KARMO-AI01 Tailscale route to the primary remote path while retaining KVE02 as fallback/recovery access.
- Added recovery classification separating routing, transport, SSH, authentication, authorization, privilege, and application-layer failures.

Do not record secret values in this log.
