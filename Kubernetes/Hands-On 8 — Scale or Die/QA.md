# Hands-On 8 — Mastery Check

Answer these without reference. Answers are below each question.

---

**Q1. What is the Metrics Server and why does HPA depend on it?**

Metrics Server is a cluster-wide aggregator of resource usage data. It scrapes CPU and memory metrics from the kubelet on each node and exposes them via the `metrics.k8s.io` API.

HPA cannot make scaling decisions without this data. Without Metrics Server, `kubectl top nodes` and `kubectl top pods` return errors, and HPA shows `<unknown>` in the TARGETS column — it has nothing to act on.

In production (AKS, EKS, GKE), Metrics Server is pre-installed. On kind, you install it manually and patch `--kubelet-insecure-tls` because kind uses self-signed certs.

---

**Q2. What does `averageUtilization: 50` mean in an HPA spec?**

It means HPA will trigger a scale-up when the average CPU utilization across all pods exceeds 50% of their **requested** CPU.

If a pod requests `200m` CPU, the threshold is `100m` (50% of 200m). If average CPU across all replicas exceeds `100m`, HPA calculates the number of pods needed to bring the average back below the threshold and scales accordingly.

Formula: `desiredReplicas = ceil(currentReplicas × (currentUtilization / targetUtilization))`

---

**Q3. What is the scale-down stabilization window and why does it exist?**

The default stabilization window for scale-down is **5 minutes**. After CPU drops below the threshold, HPA waits 5 minutes of sustained low usage before reducing replica count.

It exists to prevent **flapping** — a scenario where traffic briefly drops, HPA scales down, traffic spikes again, HPA scales up, and this cycle repeats rapidly. Flapping wastes resources and causes instability.

Scale-up has no stabilization window by default — it reacts immediately to protect availability.

---

**Q4. What is the difference between HPA and KEDA?**

| | HPA | KEDA |
|---|---|---|
| Scaling trigger | CPU / Memory only | Any metric — queues, HTTP, Prometheus, custom |
| Scale to zero | No (minimum 1) | Yes |
| Built-in | Yes | No — separate install |
| Use case | Resource-based autoscaling | Event-driven autoscaling |

Use HPA for standard web workloads. Use KEDA when scaling needs to react to external events — Azure Service Bus queue depth, RabbitMQ message count, HTTP request rate, custom Prometheus metrics.

---

**Q5. Why does HPA stop scaling at `maxReplicas` even if CPU is still above threshold?**

`maxReplicas` is a hard ceiling defined in the HPA spec. Once the cluster reaches that replica count, HPA will not create more pods regardless of CPU utilization.

This is intentional — it prevents runaway scaling from consuming all cluster resources due to a traffic spike, DDoS, or a bug that causes infinite CPU consumption. In production, `maxReplicas` is sized based on cluster node capacity and expected peak load.

---

**Q6. What happens to HPA if Metrics Server goes down?**

HPA enters a degraded state. It can no longer read CPU/memory metrics, so it stops making scaling decisions. Existing pods continue running — HPA does not scale down or terminate pods when metrics are unavailable.

The HPA object will show `<unknown>` in the TARGETS column. Once Metrics Server recovers, HPA resumes normal operation from the current replica count.

---

**Q7. How does HPA know which Deployment to scale?**

Via the `scaleTargetRef` field in the HPA spec:

```yaml
scaleTargetRef:
  apiVersion: apps/v1
  kind: Deployment
  name: php-apache
```

HPA calls the Kubernetes Scale subresource on the target Deployment to adjust `spec.replicas`. The Deployment controller then reconciles the actual pod count to match.

---

**Q8. What is the DNS name a pod uses to reach a Service inside the cluster, and what resolves it?**

Format: `<service-name>.<namespace>.svc.cluster.local`

Example: `php-apache.hpa-lab.svc.cluster.local`

**CoreDNS** resolves it. CoreDNS runs as a Deployment in `kube-system` and watches the Kubernetes API for Service and Endpoint changes. When a pod queries this DNS name, CoreDNS resolves it to the Service's ClusterIP, and kube-proxy routes traffic from the ClusterIP to one of the healthy pod endpoints.