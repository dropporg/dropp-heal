# Heal

Network monitoring for FQDN availability, latency, and filtering detection.

This chart deploys Heal as three components, each from its own image:

| Component | Image | Purpose |
| --- | --- | --- |
| api | `heal-api` | Serves the REST API. Stateless; scales freely and autoscales on CPU. |
| worker | `heal-worker` | Runs the monitoring engine: claims sites, probes them, writes metrics. |
| dashboard | `heal-dashboard` | Serves the web UI and proxies `/api` to the api component. |
| migrate | `heal-migrate` | Applies Alembic migrations as a `pre-install,pre-upgrade` hook. |

Any component can be switched off with `api.enabled`, `worker.enabled`,
`dashboard.enabled`, or `migrations.enabled`.

## Prerequisites

- Kubernetes 1.23+ and Helm 3.8+
- MySQL 8.0+ — the worker claims sites with `SELECT ... FOR UPDATE SKIP LOCKED`
- InfluxDB 2.x

Neither datastore is deployed by this chart; point `mysql.*` and `influxdb.*` at
your own instances.

## Installing

From the published repository:

```bash
helm repo add heal https://dropporg.github.io/dropp-heal
helm install heal heal/heal \
  --set secrets.databasePassword=... \
  --set secrets.influxdbToken=...
```

Or from a checkout:

```bash
helm install heal deployments/chart \
  --set secrets.databasePassword=... \
  --set secrets.influxdbToken=...
```

Uninstall with `helm uninstall heal`. The chart creates no PersistentVolumes, so
nothing is left behind.

## Scaling the worker

Worker replicas coordinate through MySQL, not memory. A worker claims due sites
with a locking read and holds a lease (`locked_by`, `locked_until`) while it
checks them, so **each site is checked once per interval however many replicas
run** — replicas share the targets rather than duplicating them. `next_check_at`
and `suspicious_streak` live on the row, so intervals stay accurate across
restarts and filtering detection keeps its evidence when another replica takes a
site over. A crashed worker's leases expire and are picked up elsewhere.

```bash
kubectl scale deploy/heal-worker --replicas=5
```

Two values matter when tuning: `worker.config.leaseSeconds` must exceed the
worst-case time to check one site, and `worker.terminationGracePeriodSeconds`
must exceed `worker.config.shutdownTimeout` so in-flight checks drain before
SIGKILL.

## Credentials

By default the chart creates a Secret from `secrets.databasePassword` and
`secrets.influxdbToken`, both required. To manage credentials yourself (External
Secrets, Vault, SOPS), set `secrets.existingSecret` to a Secret defining
`HEAL_API_DATABASE_PASSWORD`, `HEAL_API_INFLUXDB_TOKEN`, and — if Sentry is used
— `HEAL_API_SENTRY_DSN`.

## Extra configuration

Add settings without editing templates:

```yaml
extraEnvVars:                  # every component
  - name: HEAL_API_CHECK_TIMEOUT
    value: "10"
worker:
  extraEnvVars:                # one component; overrides the shared value
    - name: HEAL_API_CHECK_TIMEOUT
      value: "20"
extraSecretVars:               # merged into the chart-managed Secret
  HEAL_API_INFLUXDB_TOKEN_RO: "..."
extraEnvVarsCM: my-config      # an existing ConfigMap, loaded by every component
extraEnvVarsSecret: my-secret  # an existing Secret, loaded by every component
```

## Reaching the dashboard

The ingress fronts the dashboard by default (`ingress.service: dashboard`); set
it to `api` to expose the REST API instead.

Browsers only ever talk to the dashboard's own origin: the dashboard server
proxies `/api` to the api component, reading `HEAL_API_URL` at runtime. That
means one image works in every environment, and no CORS configuration is needed.
`dashboard.apiUrl` overrides the in-cluster target — point it at a gateway if the
API is reached some other way.

## ICMP

ICMP probes need the `NET_RAW` capability, which the default security context
drops. `worker.icmp.enabled=true` adds the capability and enables the probe
together. Heal runs normally without it.

## Parameters

### Common parameters

| Name | Description | Value |
| ---- | ----------- | ----- |
| `nameOverride` | Partially override the resource name | `""` |
| `fullnameOverride` | Fully override the resource name | `""` |
| `image.registry` | Registry prefixed to every component image, e.g. ghcr.io/dropp | `""` |
| `image.pullPolicy` | Image pull policy for every component | `IfNotPresent` |
| `image.tag` | Tag used when a component sets no tag of its own; defaults to the chart appVersion | `""` |
| `imagePullSecrets` | Secrets used to pull the component images | `[]` |
| `extraEnvVars` | Extra environment variables added to every component | `[]` |
| `extraSecretVars` | Extra sensitive values, written to the chart-managed Secret and loaded by every component | `{}` |
| `extraEnvVarsCM` | Name of an existing ConfigMap loaded as environment variables by every component | `""` |
| `extraEnvVarsSecret` | Name of an existing Secret loaded as environment variables by every component | `""` |

### API component

Serves the REST API. Stateless, so replicas scale freely.

| Name | Description | Value |
| ---- | ----------- | ----- |
| `api.enabled` | Deploy the api component | `true` |
| `api.image.repository` | API image repository | `heal-api` |
| `api.image.tag` | API image tag; falls back to image.tag, then v plus the chart appVersion | `""` |
| `api.replicaCount` | Number of api replicas; ignored when autoscaling is enabled | `3` |
| `api.service.type` | API service type | `ClusterIP` |
| `api.service.port` | API service port | `80` |
| `api.autoscaling.enabled` | Enable the HorizontalPodAutoscaler for the api | `true` |
| `api.autoscaling.minReplicas` | Lower bound for api replicas | `2` |
| `api.autoscaling.maxReplicas` | Upper bound for api replicas | `10` |
| `api.autoscaling.targetCPUUtilizationPercentage` | Target average CPU utilisation | `70` |
| `api.podDisruptionBudget.enabled` | Create a PodDisruptionBudget for the api | `true` |
| `api.podDisruptionBudget.minAvailable` | Minimum api pods kept available during disruption | `1` |
| `api.resources.requests.cpu` | CPU request for the api container | `100m` |
| `api.resources.requests.memory` | Memory request for the api container | `128Mi` |
| `api.resources.limits.memory` | Memory limit for the api container | `512Mi` |
| `api.extraEnvVars` | Extra environment variables for the api component only | `[]` |
| `api.podAnnotations` | Extra annotations for api pods | `{}` |
| `api.nodeSelector` | Node labels for api pod assignment | `{}` |
| `api.tolerations` | Tolerations for api pods | `[]` |
| `api.affinity` | Affinity rules for api pods | `{}` |

### Dashboard component

The web UI. Serves its own pages and proxies /api to the api component, so the browser only ever talks to the dashboard's origin.

| Name | Description | Value |
| ---- | ----------- | ----- |
| `dashboard.enabled` | Deploy the dashboard component | `true` |
| `dashboard.image.repository` | Dashboard image repository | `heal-dashboard` |
| `dashboard.image.tag` | Dashboard image tag; falls back to image.tag, then v plus the chart appVersion | `""` |
| `dashboard.replicaCount` | Number of dashboard replicas; ignored when autoscaling is enabled | `2` |
| `dashboard.service.type` | Dashboard service type | `ClusterIP` |
| `dashboard.service.port` | Dashboard service port | `80` |
| `dashboard.apiUrl` | URL the dashboard proxies /api to; defaults to the in-cluster api service | `""` |
| `dashboard.autoscaling.enabled` | Enable the HorizontalPodAutoscaler for the dashboard | `false` |
| `dashboard.autoscaling.minReplicas` | Lower bound for dashboard replicas | `2` |
| `dashboard.autoscaling.maxReplicas` | Upper bound for dashboard replicas | `6` |
| `dashboard.autoscaling.targetCPUUtilizationPercentage` | Target average CPU utilisation | `70` |
| `dashboard.podDisruptionBudget.enabled` | Create a PodDisruptionBudget for the dashboard | `true` |
| `dashboard.podDisruptionBudget.minAvailable` | Minimum dashboard pods kept available during disruption | `1` |
| `dashboard.resources.requests.cpu` | CPU request for the dashboard container | `100m` |
| `dashboard.resources.requests.memory` | Memory request for the dashboard container | `128Mi` |
| `dashboard.resources.limits.memory` | Memory limit for the dashboard container | `512Mi` |
| `dashboard.extraEnvVars` | Extra environment variables for the dashboard component only | `[]` |
| `dashboard.podAnnotations` | Extra annotations for dashboard pods | `{}` |
| `dashboard.nodeSelector` | Node labels for dashboard pod assignment | `{}` |
| `dashboard.tolerations` | Tolerations for dashboard pods | `[]` |
| `dashboard.affinity` | Affinity rules for dashboard pods | `{}` |

### Worker component

Runs the monitoring engine. Replicas claim sites through database leases, so each site is checked once per interval however many replicas run.

| Name | Description | Value |
| ---- | ----------- | ----- |
| `worker.enabled` | Deploy the worker component | `true` |
| `worker.image.repository` | Worker image repository | `heal-worker` |
| `worker.image.tag` | Worker image tag; falls back to image.tag, then v plus the chart appVersion | `""` |
| `worker.replicaCount` | Number of worker replicas; safe to raise, targets are shared not duplicated | `2` |
| `worker.podDisruptionBudget.enabled` | Create a PodDisruptionBudget for the worker | `true` |
| `worker.podDisruptionBudget.minAvailable` | Minimum worker pods kept available during disruption | `1` |
| `worker.terminationGracePeriodSeconds` | Time the kubelet waits before SIGKILL; keep above worker.config.shutdownTimeout | `60` |
| `worker.config.shutdownTimeout` | Seconds allowed for in-flight checks to drain on SIGTERM | `45` |
| `worker.config.leaseSeconds` | Lease duration for a claimed site; must exceed the worst-case time to check one site | `120` |
| `worker.config.claimBatchSize` | Sites claimed per scheduler tick | `50` |
| `worker.config.concurrency` | Checks a single worker runs at once | `50` |
| `worker.icmp.enabled` | Enable ICMP probes; adds the NET_RAW capability the default security context drops | `false` |
| `worker.resources.requests.cpu` | CPU request for the worker container | `200m` |
| `worker.resources.requests.memory` | Memory request for the worker container | `256Mi` |
| `worker.resources.limits.memory` | Memory limit for the worker container | `1Gi` |
| `worker.extraEnvVars` | Extra environment variables for the worker component only | `[]` |
| `worker.podAnnotations` | Extra annotations for worker pods | `{}` |
| `worker.nodeSelector` | Node labels for worker pod assignment | `{}` |
| `worker.tolerations` | Tolerations for worker pods | `[]` |
| `worker.affinity` | Affinity rules for worker pods | `{}` |

### Migration component

Applies Alembic revisions as a pre-install/pre-upgrade hook. Application pods never migrate: concurrent replicas would race on the schema.

| Name | Description | Value |
| ---- | ----------- | ----- |
| `migrations.enabled` | Run the migration Job on install and upgrade | `true` |
| `migrations.image.repository` | Migration image repository | `heal-migrate` |
| `migrations.image.tag` | Migration image tag; falls back to image.tag, then v plus the chart appVersion | `""` |
| `migrations.backoffLimit` | Retries before the migration Job is marked failed | `3` |
| `migrations.resources.requests.cpu` | CPU request for the migration container | `100m` |
| `migrations.resources.requests.memory` | Memory request for the migration container | `128Mi` |
| `migrations.resources.limits.memory` | Memory limit for the migration container | `256Mi` |
| `migrations.extraEnvVars` | Extra environment variables for the migration Job only | `[]` |

### Application configuration

| Name | Description | Value |
| ---- | ----------- | ----- |
| `config.logLevel` | Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL) | `INFO` |
| `config.logJson` | Emit structured JSON logs | `true` |
| `config.environment` | Environment name reported to Sentry | `production` |
| `config.checkInterval` | Default seconds between checks; a site may override it | `30` |
| `config.checkTimeout` | Default per-probe timeout in seconds | `5` |
| `config.checkRetries` | Retries before a probe is recorded as failed | `2` |
| `config.allowPrivateTargets` | Allow probing loopback, link-local, private and metadata addresses | `false` |
| `config.docsEnabled` | Serve the Swagger UI at /docs | `true` |
| `config.redocEnabled` | Serve ReDoc at /redoc | `true` |
| `config.corsOrigins` | Origins allowed to call the API from a browser, comma-separated; the dashboard needs its own origin here | `""` |

### Datastores

Heal does not deploy MySQL or InfluxDB; point these at your own instances.

| Name | Description | Value |
| ---- | ----------- | ----- |
| `mysql.host` | MySQL host | `mysql` |
| `mysql.port` | MySQL port | `3306` |
| `mysql.database` | MySQL database name | `heal` |
| `mysql.user` | MySQL user | `heal` |
| `influxdb.url` | InfluxDB base URL | `http://influxdb:8086` |
| `influxdb.org` | InfluxDB organisation | `heal` |
| `influxdb.bucket` | InfluxDB bucket holding probe measurements | `heal` |

### Credentials

| Name | Description | Value |
| ---- | ----------- | ----- |
| `secrets.existingSecret` | Name of an existing Secret holding the credentials; disables the chart-managed Secret | `""` |
| `secrets.databasePassword` | MySQL password; required unless existingSecret is set | `""` |
| `secrets.influxdbToken` | InfluxDB token; required unless existingSecret is set | `""` |

### Observability

| Name | Description | Value |
| ---- | ----------- | ----- |
| `sentry.dsn` | Sentry DSN; leave empty to disable error reporting | `""` |
| `sentry.tracesSampleRate` | Fraction of transactions sent to Sentry | `0.0` |
| `metrics.annotations` | Add Prometheus scrape annotations to every pod | `true` |
| `metrics.serviceMonitor.enabled` | Create a ServiceMonitor for the Prometheus Operator | `false` |
| `metrics.serviceMonitor.interval` | Scrape interval | `30s` |
| `metrics.serviceMonitor.labels` | Extra labels so your Prometheus selects the ServiceMonitor | `{}` |

### Networking and RBAC

| Name | Description | Value |
| ---- | ----------- | ----- |
| `ingress.enabled` | Create an Ingress for the api component | `false` |
| `ingress.className` | Ingress class name | `""` |
| `ingress.annotations` | Ingress annotations | `{}` |
| `ingress.service` | Component the ingress routes to: dashboard or api | `dashboard` |
| `ingress.hosts` | Ingress hosts and paths | `[{host: heal.local, paths: [{path: /, pathType: Prefix}]}]` |
| `ingress.tls` | Ingress TLS configuration | `[]` |
| `serviceAccount.create` | Create a ServiceAccount for the components | `true` |
| `serviceAccount.name` | ServiceAccount name; generated when empty | `""` |
| `serviceAccount.annotations` | ServiceAccount annotations, e.g. for workload identity | `{}` |

### Security contexts

| Name | Description | Value |
| ---- | ----------- | ----- |
| `podSecurityContext.runAsNonRoot` | Refuse to run the containers as root | `true` |
| `podSecurityContext.runAsUser` | UID the containers run as; matches the image user | `10001` |
| `podSecurityContext.seccompProfile.type` | Seccomp profile applied to the pods | `RuntimeDefault` |
| `securityContext.allowPrivilegeEscalation` | Allow privilege escalation inside the containers | `false` |
| `securityContext.readOnlyRootFilesystem` | Mount the container root filesystem read-only | `true` |
| `securityContext.capabilities.drop` | Linux capabilities dropped from the containers | `[ALL]` |

