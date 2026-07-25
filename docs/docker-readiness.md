# Docker readiness

Aurora ships a two-service local stack in `docker-compose.yml`: the FastAPI
backend on port 8000 and the Vite frontend on port 5173. The Compose file and
the two Dockerfiles share a small contract covering build contexts, startup
commands, ports, source mounts, the backend taxonomy path, and the frontend's
backend dependency.

Run the offline contract check from the repository root:

```text
python scripts/docker_audit.py
```

The audit uses only the Python standard library. It catches drift between the
checked-in files and prints `DOCKER STATIC AUDIT PASS` when the contract is
consistent. It intentionally does not invoke Docker, build images, pull
packages, or start containers. A passing audit is therefore readiness evidence,
not runtime verification; the self-audit remains PARTIAL until a Docker host
successfully runs the stack.
