# Hands-On 14 — Mastery Check

Answer these without reference. Answers are below each question.

---

**Q1. What is Prometheus and how does it collect metrics (pull vs push)?**

Prometheus is a time-series database and monitoring system. It collects metrics by **pulling** — on a configured schedule (e.g., every 15 seconds), Prometheus makes an HTTP GET request to each target's `/metrics` endpoint, parses the response, timestamps each data point, and stores it.

```
Prometheus → GET http://10.244.0.13:9113/metrics → parses response → stores time-series
```

It does **not** wait for applications to push data. This is a fundamental design choice:
- **If an app dies**, Prometheus detects it immediately — the scrape fails, `up == 0` is recorded
- **No client-side buffering** needed — your app doesn't need retry logic or a Prometheus client library (just expose `/metrics`)
- **Prometheus controls the schedule** — no thundering herd of apps pushing simultaneously
- **Service discovery** (via ServiceMonitor) handles dynamic pod IPs automatically — pods come and go, Prometheus adapts

The `/metrics` endpoint returns plain text in Prometheus exposition format:
```
# TYPE nginx_up gauge
nginx_up 0
# TYPE process_resident_memory_bytes gauge
process_resident_memory_bytes 17268736
```

Each line is a metric name, optional labels in `{}`, and a numeric value.

---

**Q2. What is the role of Grafana in the monitoring stack?**

Grafana is a **pure visualization layer**. It has no storage, no collection logic, and no alerting evaluation of its own (in this stack — Grafana does have its own alerting, but the kube-prometheus-stack uses Prometheus + Alertmanager instead).

What Grafana does:
- Connects to Prometheus as a **data source**
- Runs PromQL queries behind the scenes when you load a dashboard
- Renders the results as graphs, tables, gauges, heatmaps
- Provides a UI for exploring metrics ad-hoc (Explore tab)
- Pre-built dashboards come bundled via the Helm chart (auto-loaded by sidecar containers)

What Grafana does **not** do:
- Does not scrape metrics
- Does not store time-series data
- Does not evaluate alert rules (in this stack)
- Does not know about ServiceMonitors or PrometheusRules

**Analogy:** Prometheus is the security camera system (records everything). Grafana is the monitor screens (displays recordings). Cameras work without screens. Screens are useless without cameras.

---

**Q3. What is a ServiceMonitor and why is it needed?**

A ServiceMonitor is a **Custom Resource Definition (CRD)** introduced by the Prometheus Operator. It tells Prometheus which Service to scrape, which port, and at what interval.

```yaml
spec:
  selector:
    matchLabels:
      app: sample-app       # Find the Service with this label
  endpoints:
  - port: metrics            # Scrape the port named "metrics" (9113)
    interval: 15s            # Every 15 seconds
```

**Why it's needed:** Prometheus doesn't auto-discover your application. Without a ServiceMonitor, Prometheus has no idea your app exists or that it exposes a `/metrics` endpoint. The ServiceMonitor is the bridge.

**Connection chain:**
```
ServiceMonitor (selector: app=sample-app)
    → finds Service (labels: app=sample-app)
        → Service has Endpoints (pod IPs: 10.244.0.13, 10.244.0.14)
            → Prometheus scrapes each pod at :9113/metrics
```

The Prometheus **Operator** watches for ServiceMonitor CRDs. When you `kubectl apply` a ServiceMonitor, the Operator detects it and updates Prometheus's scrape configuration — no restart needed, no manual config file edits.

---

**Q4. What is the difference between kube-state-metrics and node-exporter?**

They expose completely different types of metrics:

| | kube-state-metrics | node-exporter |
|---|---|---|
| **What it monitors** | Kubernetes objects (API-level) | Node hardware (OS-level) |
| **Example metrics** | `kube_pod_status_phase`, `kube_deployment_spec_replicas`, `kube_node_status_condition` | `node_cpu_seconds_total`, `node_memory_MemAvailable_bytes`, `node_disk_io_time_seconds_total` |
| **Data source** | Kubernetes API server | Linux `/proc` and `/sys` filesystems |
| **Deployment** | Single Deployment (1 pod) | DaemonSet (1 pod per node) |
| **Answers** | "How many pods are in CrashLoopBackOff?" "Is this Deployment at desired replicas?" | "Is this node running out of CPU?" "How much disk space is left?" |

**kube-state-metrics** tells you about Kubernetes state — is the cluster healthy from an orchestration perspective?

**node-exporter** tells you about hardware — is the machine healthy from an infrastructure perspective?

Both feed into Prometheus. The pre-built Grafana dashboards use metrics from both to give you a complete picture.

---

**Q5. What is the Prometheus Operator and what CRDs does it watch?**

The Prometheus Operator is a Kubernetes controller that manages Prometheus instances declaratively via CRDs. Instead of editing Prometheus config files manually, you create Kubernetes objects and the Operator translates them into Prometheus configuration.

**CRDs it watches:**

| CRD | Purpose |
|---|---|
| **ServiceMonitor** | Defines which Services to scrape and how |
| **PodMonitor** | Like ServiceMonitor but targets pods directly (no Service needed) |
| **PrometheusRule** | Defines alerting and recording rules as PromQL expressions |
| **Prometheus** | Defines a Prometheus instance itself (replicas, retention, storage, resource limits) |
| **Alertmanager** | Defines an Alertmanager instance (replicas, config) |

**Workflow:** You `kubectl apply` a ServiceMonitor → Operator detects it → Operator updates Prometheus's scrape config → Prometheus starts scraping the new target. No restart. No manual config editing. This is the operator pattern — extending Kubernetes with domain-specific controllers.

---

**Q6. What does `serviceMonitorNamespaceSelector.any=true` do and why is it needed?**

By default, Prometheus only watches for ServiceMonitors **in its own namespace** (typically `monitoring`). If your app lives in `app-lab` and you create a ServiceMonitor there, Prometheus won't see it.

`serviceMonitorNamespaceSelector.any=true` tells Prometheus to watch **all namespaces** for ServiceMonitors.

Similarly, `ruleNamespaceSelector.any=true` does the same for PrometheusRules.

**Without these flags:**
```
ServiceMonitor in app-lab → Prometheus in monitoring → ❌ Not discovered
```

**With these flags:**
```
ServiceMonitor in app-lab → Prometheus in monitoring → ✅ Discovered and scraped
```

In production, you might restrict this to specific namespaces instead of `any=true` — for example, only watch namespaces with a specific label. But for most setups, `any=true` is the practical default.

There are four related flags:
- `serviceMonitorSelectorNilUsesHelmValues=false` — pick up ANY ServiceMonitor (not just ones with Helm labels)
- `serviceMonitorNamespaceSelector.any=true` — watch ALL namespaces for ServiceMonitors
- `ruleSelectorNilUsesHelmValues=false` — pick up ANY PrometheusRule
- `ruleNamespaceSelector.any=true` — watch ALL namespaces for PrometheusRules

---

**Q7. What is PromQL and what does `rate(metric[1m])` calculate?**

PromQL (Prometheus Query Language) is the query language for Prometheus. Used in dashboards, alerts, and ad-hoc queries.

**`rate(metric[1m])` calculates the per-second average rate of change** of a counter metric over the last 1 minute.

Example: `rate(promhttp_metric_handler_requests_total{namespace="app-lab"}[1m])` returned `0.066` in this lab. That means 0.066 requests per second ≈ ~4 requests per minute — which matches Prometheus scraping every 15 seconds.

**Key PromQL concepts:**

| Syntax | What It Does |
|---|---|
| `{namespace="app-lab"}` | Label filter — only return metrics matching this label |
| `[1m]` | Range vector — use the last 1 minute of data points |
| `rate()` | Per-second rate of change (for counters only — counters only go up) |
| `sum by (label)` | Aggregate values grouped by a label |
| `count()` | Count the number of time series matching a query |
| `avg()` | Average across matching time series |
| `histogram_quantile()` | Calculate percentiles from histogram metrics (e.g., p99 latency) |

**Counter vs Gauge:**
- **Counter** — only goes up (requests served, errors occurred). Use `rate()` to get useful per-second values.
- **Gauge** — goes up and down (current memory usage, active connections). Read directly without `rate()`.

---

**Q8. What is the sidecar pattern and how is it used for observability?**

The sidecar pattern places **two containers in one pod** that share the same network namespace (localhost) and optionally the same volumes. One container is the main app, the other handles a cross-cutting concern.

**Observability sidecar in this lab:**
```
Pod
├── nginx (main app, serves traffic on :80)
└── nginx-prometheus-exporter (sidecar, exposes /metrics on :9113)
```

The exporter connects to `localhost/stub_status` (nginx's internal status page) and translates it into Prometheus-format metrics. Your app code doesn't need to know anything about Prometheus — the sidecar handles the integration.

**Why sidecar instead of instrumenting the app directly?**
- Many apps (nginx, MySQL, PostgreSQL, Redis) don't natively expose Prometheus metrics
- Sidecar adds observability without modifying the app image
- Separation of concerns — app team owns the app container, platform team owns the exporter sidecar
- Exporter can be updated independently of the app

**Other common sidecars:**
- Log shipping (Fluentd/Fluent Bit sidecar ships logs to Elasticsearch)
- Proxy (Envoy sidecar in service meshes like Istio)
- Config reloading (Prometheus's own config-reloader sidecar)

---

**Q9. What is a PrometheusRule and what does `for: 1m` mean?**

A PrometheusRule is a CRD that defines alerting (and recording) rules as PromQL expressions. The Prometheus Operator watches for these and injects them into Prometheus's rule evaluation engine.

```yaml
rules:
- alert: SampleAppDown
  expr: nginx_up{namespace="app-lab"} == 0
  for: 1m
  labels:
    severity: critical
```

**`for: 1m`** means the PromQL expression must evaluate to `true` **continuously for 1 minute** before the alert transitions from `PENDING` to `FIRING`.

**Why this matters:** Without `for`, a single failed scrape would fire an alert. If nginx was restarting and down for 5 seconds, you'd get a page for a non-issue. `for: 1m` absorbs transient blips — only genuine sustained failures trigger notifications.

**The `labels.severity` field** is used by Alertmanager's routing config to decide where to send the alert. A production setup might route `critical` to PagerDuty (pages on-call), `warning` to a Slack channel, and `info` to a dashboard only.

---

**Q10. What is the alert lifecycle (4 states)?**

```
INACTIVE → PENDING → FIRING → INACTIVE (resolved)
```

| State | Meaning |
|---|---|
| **INACTIVE** | PromQL expression evaluates to false. No issue detected. |
| **PENDING** | Expression is true, but `for` duration hasn't elapsed yet. Waiting. |
| **FIRING** | Expression has been true for the full `for` duration. Alert sent to Alertmanager. |
| **INACTIVE (resolved)** | Expression returned to false. Alertmanager sends a "resolved" notification. |

**Example from this lab:**
1. `nginx_up == 0` starts evaluating → `UNKNOWN` (first evaluation)
2. Expression is true → `PENDING` (1-minute timer starts)
3. Still true after 1 minute → `FIRING (2)` (one alert per pod, sent to Alertmanager)
4. If we enabled `stub_status` and `nginx_up` became 1 → `INACTIVE` (resolved)

The `PENDING` state is the buffer. It prevents alert storms from transient issues. In production, `for` values are tuned per alert — a disk-full alert might use `for: 5m` (disks don't fill instantly), while a critical API-down alert might use `for: 30s`.

---

**Q11. Why does Prometheus use pull-based scraping instead of push?**

Five concrete reasons:

1. **Failure detection is automatic** — if a scrape fails, Prometheus records `up == 0`. You know immediately when a target is down. With push, silence could mean "nothing to report" or "the app is dead" — you can't distinguish.

2. **Prometheus controls the schedule** — no thundering herd of 500 apps pushing metrics at the same time. Prometheus distributes scrapes evenly across the interval.

3. **No client-side complexity** — your app just needs to serve an HTTP endpoint. No buffering, no retry logic, no Prometheus client library required (though libraries exist for custom metrics). A simple `/metrics` handler returning text is sufficient.

4. **Dynamic targets via service discovery** — pods come and go. Prometheus + ServiceMonitor adapts automatically. With push, each new pod would need to know where to push to, handle connection failures, and buffer during outages.

5. **Easy to debug** — you can `curl` the `/metrics` endpoint yourself to see exactly what Prometheus sees. With push, debugging requires intercepting the push pipeline.

**Exception:** Some use cases genuinely need push — short-lived batch jobs that exit before Prometheus scrapes them. For these, Prometheus provides the **Pushgateway** — the job pushes metrics to the gateway, and Prometheus scrapes the gateway.

---

**Q12. What happens to all metrics data when you delete the kind cluster and how is this solved in production?**

Deleting the kind cluster destroys everything — Prometheus's time-series database, Grafana's dashboards, Alertmanager's state, all configuration. Everything lived inside the cluster with no persistent storage.

**Production solutions:**

**For Prometheus data:**
- Use **PersistentVolumeClaims (PVCs)** backed by cloud disks (Azure Managed Disk, AWS EBS, GCP Persistent Disk). Prometheus data survives pod restarts.
- Set retention: `--storage.tsdb.retention.time=30d` (default 15 days)
- For long-term storage beyond retention, use **Thanos** or **Cortex** as a remote write backend — Prometheus writes to object storage (Azure Blob, S3) for months/years of data

**For Grafana dashboards:**
- Store dashboards as **ConfigMaps** in Git — the sidecar container (`grafana-sc-dashboard`) auto-loads them
- Never create dashboards manually in the Grafana UI — they'll be lost on pod restart
- Grafana can also use a database (PostgreSQL) for persistent dashboard storage in production

**For Alertmanager config:**
- Store routing configuration in Git as part of the Helm values
- Alertmanager's silence state can use PVCs for persistence

**For the entire stack:**
- The Helm values file (`values-prod.yaml`) is your infrastructure-as-code for the monitoring stack
- Store it in Git alongside your app charts
- ArgoCD (Hands-On 15) deploys and maintains the monitoring stack from Git — if the cluster is rebuilt, ArgoCD reinstalls everything automatically

---

**Q13. What is the difference between ServiceMonitor and PodMonitor?**

Both tell Prometheus what to scrape. The difference is the target:

| | ServiceMonitor | PodMonitor |
|---|---|---|
| **Targets** | A Kubernetes Service | Pods directly |
| **Selector** | Matches Service labels | Matches Pod labels |
| **Requires** | A Service in front of pods | No Service needed |
| **Use case** | Most common — apps exposed via Services | Sidecar exporters, batch jobs, pods without Services |

**ServiceMonitor** finds a Service → gets its Endpoints (pod IPs) → tells Prometheus to scrape each pod.

**PodMonitor** finds pods directly by label → tells Prometheus to scrape them. Useful when there's no Service (e.g., a DaemonSet exporter or a batch job with metrics).

In practice, ServiceMonitor covers 90%+ of use cases because most apps have a Service.

---

**Q14. What is the complete end-to-end flow from app deployment to alert firing?**

Full chain, nothing skipped:

```
1. Deploy app with exporter sidecar (2 containers per pod)
2. Create Service exposing port "metrics" (9113)
3. Create ServiceMonitor selecting the Service by label
4. Prometheus Operator detects ServiceMonitor → updates Prometheus scrape config
5. Prometheus starts scraping each pod's :9113/metrics every 15s
6. Metrics stored in Prometheus's time-series database
7. Create PrometheusRule with PromQL expression (nginx_up == 0)
8. Operator injects rule into Prometheus's rule evaluation
9. Prometheus evaluates rule on every scrape cycle
10. Expression true → alert enters PENDING state
11. Expression true for full "for" duration (1m) → alert enters FIRING
12. Prometheus sends alert to Alertmanager
13. Alertmanager routes alert based on severity label → Slack/PagerDuty/email
14. Grafana dashboards show the same metrics as real-time graphs
15. Engineer sees alert, opens Grafana, drills into the affected namespace/pod
16. Root cause identified, fix deployed, nginx_up becomes 1
17. Prometheus evaluates rule → expression false → alert resolves → INACTIVE
18. Alertmanager sends "resolved" notification
```

This entire chain — from metrics exposure to alert resolution — runs automatically. No human intervention needed for detection and notification. The engineer only enters at step 15.