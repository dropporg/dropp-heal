# Heal

Heal is a network monitoring service. It continuously checks the availability,
reachability, and latency of configured FQDNs, and applies heuristics to flag
targets that may be filtered or blocked.

Target configuration and the latest state live in MySQL; historical latency and
availability measurements go to InfluxDB.

## Quick start

```bash
git clone git@github.com:dropporg/dropp-heal.git
cd dropp-heal
```

Run the whole stack in containers:

```bash
docker compose up -d --build   # datastores, migrations, api, worker and dashboard
open http://localhost:3000     # the dashboard; the API is on :8000
```

Or run the datastores in containers and the app on the host:

```bash
cp .env.example .env          # defaults match the local infra stack
just infra-up                 # mysql + influxdb only
just upgrade                  # apply migrations
just run                      # api on :8000
just run-worker               # monitoring engine on :8001
just run-dashboard            # dashboard on :3000
```

The dashboard proxies `/api` to `HEAL_API_URL` server-side, so the browser only
ever calls the dashboard's origin and no CORS setup is needed. Set
`HEAL_API_CORS_ORIGINS` on the API only if a browser calls it directly.

API documentation is at `/docs`, the schema at `/openapi.json`.

On NixOS, run commands inside `nix-shell` — greenlet needs `libstdc++` on the
library path, which `shell.nix` provides.

## Commands

`just` lists every recipe. The common ones: `just test`, `just format`,
`just check`, `just revision "message"`, `just upgrade`, `just docker-build`.

The dashboard has its own suite: `cd dashboard && npm test`.

CI runs on every push and pull request:

| Workflow | Checks |
| --- | --- |
| `tests.yml` | pytest, vitest |
| `lint.yml` | isort, black, ruff; eslint, tsc, next build |
| `security.yml` | bandit, pip-audit, npm audit, gitleaks over history and tree (also weekly) |
| `build.yml` | builds and pushes component images to ghcr.io |
| `chart.yml` | lints, renders and packages the chart; publishes it on a `helm/*` tag |

### Tags and releases

Every tag is `<app>/<version>`, where the version is `X.Y.Z` or `vX.Y.Z`, with an
optional `-beta.N` style prerelease suffix.

| Tag | Effect |
| --- | --- |
| `api/v0.1.1`, `worker/v0.1.23`, `migrate/1.0.0-beta.1`, `dashboard/v0.1.4` | builds and publishes that one image |
| `release/v1.0.0` | the product-wide version; becomes the chart's `appVersion` |
| `helm/v1.2.0` | publishes the chart at that version |

### Publishing images

A push to `main` builds only the components whose files changed, publishing two
tags:

```
ghcr.io/dropporg/heal-api:<full commit sha>
ghcr.io/dropporg/heal-api:nightly          # newest unstable build
```

A change under `api/` rebuilds the api, worker and migrate images, since they
share that package; a change under `dashboard/` rebuilds only the dashboard.
Changes under `.github/`, `README.md` or the chart build nothing.

A component tag publishes the commit sha, the version verbatim, and — for a
stable release only — `latest`:

```bash
git tag worker/v0.1.23        # :<sha>, :v0.1.23, :latest
git tag dashboard/v1.0.0-beta.5   # :<sha>, :v1.0.0-beta.5   (latest untouched)
```

A prerelease never moves `latest`, so anything tracking `latest` stays on the
last stable build.

Push release tags **one at a time**. GitHub creates no tag events at all when
more than three tags arrive in a single push, so a batched push silently builds
nothing:

```bash
for c in api worker dashboard migrate; do
  git push origin "$c/v0.0.1-beta.1"
done
```

To publish without touching a component's files, run the workflow by hand:

```bash
gh workflow run build.yml -f component=dashboard -f version=v0.1.0-rc.1
gh workflow run build.yml                        # every component, sha + nightly
```

Publishing is gated on the `CI_TESTING_ENABLED` repository variable:

```bash
gh variable set CI_TESTING_ENABLED --body true    # publish
gh variable set CI_TESTING_ENABLED --body false   # stop publishing
```

Only `true` (or leaving it unset) publishes; any other value builds nothing and
the job still passes, saying why. When a push changes no component the build job
still runs and passes, reporting "nothing to build".

Reproduce the Python gates locally with `just check`, `just lint`,
`just audit`, and `just secrets`; the dashboard with `npm run lint`, `npm run typecheck`, and
`npm audit`. Lint rules live in `ruff.toml`.

## Endpoints

| Path | Purpose |
| --- | --- |
| `POST /api/v1/sites` | Register a target |
| `GET /api/v1/sites` | List, with pagination, status/active filters, and search |
| `GET /api/v1/sites/{id}` | Configuration and latest status |
| `PATCH /api/v1/sites/{id}` | Update monitoring configuration |
| `DELETE /api/v1/sites/{id}` | Remove a target |
| `POST /api/v1/sites/{id}/enable`, `/disable` | Toggle monitoring |
| `POST /api/v1/sites/{id}/check` | Probe immediately, without waiting for the interval |
| `GET /api/v1/sites/{id}/status` | Current state plus the latest reading per probe |
| `GET /api/v1/sites/{id}/metrics` | Historical series for graphing |
| `GET /probe/live`, `/probe/ready` | Container liveness and readiness |
| `GET /metrics` | Prometheus metrics about Heal itself |

Every `/api/v1` response uses the same envelope:

```json
{
  "result": {},
  "status": { "code": 100, "message": "OK" },
  "_metadata": ""
}
```

`status.code` is an application code (100 OK, 101 not implemented, 102 invalid
schema, 103 database error, 104 not found, 105 already exists, ...) and is
independent of the HTTP status.

### Querying metrics for graphs

```
GET /api/v1/sites/{id}/metrics?start=-2d&aggregation=p95&window=1h&field=latency_ms
```

`start` and `end` accept a relative duration (`-2d`, `-6h`) or an RFC 3339
timestamp. `aggregation` is one of `raw`, `mean`, `min`, `max`, `p50`, `p95`,
`p99`; `window` sets the bucket size when aggregating. The response contains one
time-sorted series per probe type and field, ready to plot directly.

## Components

Heal is built as three components, each with its own image, deployed and scaled
independently:

| Component | Image | Entrypoint | Role |
| --- | --- | --- | --- |
| api | `heal-api` | `main.py` | Serves the REST API. Stateless, scales freely. |
| worker | `heal-worker` | `worker.py` | Runs the monitoring engine. Serves only `/probe/*` and `/metrics`. |
| dashboard | `heal-dashboard` | `dashboard/` | Serves the web UI and proxies `/api` to the api component. |
| migrate | `heal-migrate` | `alembic upgrade head` | Applies migrations as a Job before a rollout. |

```bash
just docker-build      # builds all four
```

Dockerfiles live in `deployments/docker/`, one per component, built from the
repository root.

### Why the worker scales safely

Worker replicas coordinate through the database, not in memory:

- A worker claims due sites with a locking read (`SELECT ... FOR UPDATE SKIP
  LOCKED`) and stamps `locked_by` and `locked_until` on each row. Concurrent
  workers take disjoint batches, so **a site is checked once per interval no
  matter how many replicas run**.
- `next_check_at` lives on the row, so intervals do not drift across restarts,
  rescheduling, or scale events.
- `suspicious_streak` lives on the row too, so filtering detection keeps
  accumulating evidence even when a different replica picks the site up.
- If a worker dies mid-check its lease expires and another replica takes the
  site over; on a clean shutdown the lease is released immediately.

Set `HEAL_API_LEASE_SECONDS` above the worst-case time to check one site, and
`terminationGracePeriodSeconds` above `HEAL_API_SHUTDOWN_TIMEOUT` so in-flight
checks can drain before SIGKILL.

## Helm chart

The chart is published as a plain HTTP repository on GitHub Pages, so no
registry login is needed:

```bash
helm repo add heal https://dropporg.github.io/dropp-heal
helm repo update
helm install heal heal/heal \
  --set secrets.databasePassword=... \
  --set secrets.influxdbToken=...
```

`Chart.yaml` holds `__chartVersion__` and `__appVersion__` placeholders, which
the pipeline stamps before it lints or packages, so the two versions come from
tags rather than from an edited file:

| Version | Comes from | Example |
| --- | --- | --- |
| chart `version` | the `helm/*` tag being pushed | `helm/v1.2.0` → `1.2.0` |
| chart `appVersion` | the newest `release/*` tag | `release/v0.1.0` → `0.1.0` |

```bash
git tag release/v0.1.0 && git push origin release/v0.1.0  # the product version
git tag helm/v1.2.0    && git push origin helm/v1.2.0     # publishes heal-1.2.0.tgz
```

Both drop their leading `v`, so `helm install --version 1.2.0` resolves. The
chart adds the `v` back when it builds an image reference, because the images
keep it: `appVersion: 0.1.0` renders `heal-api:v0.1.0`. Pin `api.image.tag` and
friends when a component's version differs from the product release.

Pushes and pull requests lint, render and package with a `0.0.0-sha.<short>`
version and publish nothing. Publishing also respects `CI_TESTING_ENABLED`.
Locally, `just chart-lint` stamps a throwaway version into a copy and lints it.

The chart in `deployments/chart/` deploys all four components, and can also be
installed straight from a checkout:

```bash
helm install heal deployments/chart \
  --set secrets.databasePassword=... \
  --set secrets.influxdbToken=...
```

`values.yaml` documents every parameter with `@section` and `@param` annotations.
Extra configuration goes in without editing templates: `extraEnvVars` (chart-wide)
and `api.extraEnvVars` / `worker.extraEnvVars` / `migrations.extraEnvVars` (one
component), `extraSecretVars` for sensitive additions to the managed Secret, and
`extraEnvVarsCM` / `extraEnvVarsSecret` to load an existing ConfigMap or Secret.

Migrations run as a `pre-install,pre-upgrade` hook from their own image, so
application pods never migrate — several replicas running `alembic upgrade` at
once would race on the schema.

Point `secrets.existingSecret` at a Secret you manage (External Secrets, Vault,
SOPS) to keep credentials out of values. Each component can be switched off with `api.enabled`, `worker.enabled`,
`dashboard.enabled`, or `migrations.enabled`. The ingress fronts the dashboard by
default; `ingress.service=api` exposes the REST API instead.

ICMP needs `NET_RAW`, which the default security context drops. Setting
`worker.icmp.enabled=true` adds the capability back and enables the probe.

## Probes

DNS, ICMP, TCP, HTTP, and HTTPS. ICMP needs raw socket permissions that
containers often lack, so it is disabled by default and Heal runs without it.

Probes implement a single interface (`api/probes/base.py`), so new check types —
traceroute, DoH, QUIC, certificate expiry — only need a subclass and a registry
entry.

## Filtering detection

Heal never claims filtering with certainty. A target must look suspicious across
several consecutive rounds before it is reported as `suspected_filtered`, and
signals are combined rather than taken alone — ICMP failing while HTTPS works is
explicitly *not* treated as filtering. Raw per-probe measurements are kept in
InfluxDB so the heuristics can be improved later.

## Configuration

All configuration comes from `HEAL_API_*` environment variables, validated with
Pydantic Settings; see `.env.example` for the full list. Because Heal makes
outbound requests to user-supplied hostnames, loopback, link-local, private, and
cloud metadata addresses are rejected as targets unless
`HEAL_API_ALLOW_PRIVATE_TARGETS=true`.

## Layout

```
api/
├── config/        settings
├── cruds/         database queries
├── db/            mysql connector, declarative base
├── models/        sqlalchemy models
├── observability/ prometheus metrics
├── probes/        dns, icmp, tcp, http probes
├── routers/       http endpoints
├── schemas/       request and response models
├── tasks/         scheduler, worker, filtering heuristics
├── tsdb/          influxdb connector and flux queries
└── utils/         response envelope, logging, network guards
migrations/        alembic revisions
tests/
dashboard/         next.js web ui
deployments/       dockerfiles and helm chart
```
