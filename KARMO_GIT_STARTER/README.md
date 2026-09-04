# KARMO Platform

Private source and governance repository for KARMO. This repository contains only sanitized source, tests, architecture decisions, evaluation fixtures, and runbooks.

It must never contain secrets, production conversation data, customer/private documents, database dumps, Qdrant snapshots, model files, or virtual environments.

## Operating rule

Claude is the isolated development/test implementer. Codex is the independent design, security, and evidence reviewer. Natalie is the only production approver.

## Current status

KARMO v0.5 is frozen and H0.0 is verified. H0.1 is in isolated failure-matrix testing; production change is not authorized.
