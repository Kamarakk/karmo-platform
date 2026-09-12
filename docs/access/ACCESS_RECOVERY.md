# KARMO Access Recovery

Use this order. Do not skip directly to passwords, keys, or service changes.

1. **Context** — where is the operator/agent: HOME, OFFICE, TRAVEL_REMOTE, LOCAL_CONSOLE, or AGENT_REMOTE?
2. **Target identity** — confirm hostname/asset role from `HOST_ACCESS_REGISTRY.yaml`.
3. **Route** — resolve the approved path from `CONNECTION_PATHS.yaml`.
4. **Network reachability** — determine whether the target path/IP is routable from the current context.
5. **Transport** — verify Tailscale/LAN/jump-host connectivity separately from SSH.
6. **SSH reachability** — verify port 22 and key exchange are reached before judging credentials.
7. **Authentication** — resolve the expected user/key from `AUTH_METHOD_REGISTRY.yaml`; never request or print secrets.
8. **Authorization/privilege** — distinguish successful login from sudo/production authority.
9. **Application access** — only after the host path works, troubleshoot VS Code, Claude Code, Remote Desktop Commander, or another application layer.
10. **Fallback** — use the documented fallback path; do not invent a new tool merely because the preferred path is unavailable.

## STOP conditions
Stop and report before modifying anything if:
- current host/IP evidence conflicts with the registry;
- the required path would need a new route, firewall rule, credential, package, or daemon not already approved;
- recovery would require password reset, key replacement, sshd configuration changes, or production service restart;
- a read-only diagnosis reveals a write requirement outside current authorization.

## Common classification
- `NETWORK_UNREACHABLE`: no route/TCP reachability; credentials were not tested.
- `TRANSPORT_UNAVAILABLE`: Tailscale/LAN/jump host unavailable.
- `SSH_UNREACHABLE`: network works but SSH endpoint does not respond.
- `AUTHENTICATION_REJECTED`: SSH reached the host and rejected the presented identity.
- `AUTHORIZATION_DENIED`: identity authenticated but lacks requested permission.
- `PRIVILEGE_REQUIRED`: login works; sudo/operator action is required.
- `APPLICATION_LAYER_FAILURE`: SSH/path works; VS Code/Claude/RDC layer fails.

Never treat one category as another.