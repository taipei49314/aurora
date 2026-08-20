# Docker readiness

Aurora ships a two-service local stack in `docker-compose.yml`: the FastAPI
backend on port 8000 and the Vite frontend on port 5173. The Compose file and
the two Dockerfiles share a small contract covering build contexts, startup
commands, ports, source mounts, the backend taxonomy path, and the frontend's
backend dependency. The Vite proxy defaults to `http://localhost:8000` for a
host-local `make frontend` run. Compose overrides `AURORA_API_PROXY_TARGET` to
`http://backend:8000`, using the backend service name on the Compose network.

Run the offline contract check from the repository root:

```text
python scripts/docker_audit.py
```

The audit uses only the Python standard library. It catches drift between the
checked-in files and prints `DOCKER STATIC AUDIT PASS` when the contract is
consistent. It intentionally does not invoke Docker, build images, pull
packages, or start containers. A passing audit is therefore readiness evidence,
not runtime verification.

On a Docker host, verify the live proxy path as well as container startup:

```text
docker compose up --build -d
curl http://localhost:5173/api/health
docker compose down -v
```

The health request must return HTTP 200 from the backend through the frontend
proxy. This runtime smoke check passed on 2026-08-21; repeat it after changes to
Compose, either Dockerfile, or the Vite server configuration.
