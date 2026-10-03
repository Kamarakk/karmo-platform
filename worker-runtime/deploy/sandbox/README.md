# KARMO code sandbox (Worker02)

The worker's `code_run` capability writes each job (main.py plus input files) into
`/var/lib/karmo/sandbox/jobs/` and waits for `result.json`. The separate root
service `karmo-sandbox-runner` runs each job once in a throwaway container:
no network, read-only root, 512 MB memory, 1 CPU, 64 processes, all
capabilities dropped, user nobody, input mounted read-only, 60-second limit.
The worker service never gets Docker access.

Install, on Worker02 (after the worker code is updated):

```
sudo install -d -m 2770 -o root -g karmo /var/lib/karmo/sandbox /var/lib/karmo/sandbox/jobs
sudo docker pull docker.io/library/python:3.12-slim
sudo install -m 644 karmo-sandbox-runner.service /etc/systemd/system/
sudo install -d /etc/systemd/system/karmo-worker02.service.d
sudo install -m 644 karmo-worker02-sandbox.conf /etc/systemd/system/karmo-worker02.service.d/sandbox.conf
sudo systemctl daemon-reload && sudo systemctl enable --now karmo-sandbox-runner
```

Undo: `sudo systemctl disable --now karmo-sandbox-runner`, then remove the two unit files and run `daemon-reload`.
