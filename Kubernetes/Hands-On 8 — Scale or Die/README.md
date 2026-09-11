# Hands-On 8 — Scale or Die

## What This Lab Is About

Kubernetes doesn't need you to scale your app manually. You declare thresholds — the control plane does the rest.

This lab teaches you **Horizontal Pod Autoscaling**: how Kubernetes monitors CPU metrics, calculates the desired replica count, and scales your Deployment up and down automatically based on real load.

---

## Concepts Covered

- Metrics Server — exposes CPU/memory data to the control plane
- HPA (HorizontalPodAutoscaler) — scales pod count based on resource thresholds
- Load Testing — generating real traffic to trigger autoscaling
- Scale-down stabilization window — why Kubernetes waits before scaling down
- KEDA concept — event-driven autoscaling beyond CPU/memory

---

## Prerequisites

- kind installed (`winget install Kubernetes.kind`)
- kubectl installed
- Docker running

---

## Cluster Setup

```bash
kind create cluster --name k8s-labs
kubectl get nodes
```

Expected output:
```
NAME                     STATUS   ROLES           AGE   VERSION
k8s-labs-control-plane   Ready    control-plane   Xs    v1.x.x
```

---

## Files in This Lab

| File | Purpose |
|---|---|
| `namespace.yaml` | Creates namespace `hpa-lab` |
| `deployment.yaml` | Deploys `hpa-example` PHP app with CPU requests/limits |
| `service.yaml` | ClusterIP Service exposing the app internally |
| `hpa.yaml` | HPA targeting 50% CPU utilization, min 1 / max 5 replicas |

---

## Step-by-Step

### 1. Create Namespace

```bash
kubectl apply -f namespace.yaml
kubectl get namespaces
```

---

### 2. Install Metrics Server

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

Patch for kind (self-signed TLS):

```bash
kubectl patch deployment metrics-server -n kube-system --type='json' -p='[
  {
    "op": "add",
    "path": "/spec/template/spec/containers/0/args/-",
    "value": "--kubelet-insecure-tls"
  }
]'
```

Verify:

```bash
kubectl top nodes
```

Expected: CPU and memory usage for the node. If metrics not available yet, wait 30s and retry.

---

### 3. Deploy the App

```bash
kubectl apply -f deployment.yaml
kubectl get pods -n hpa-lab
```

Expected: 1 pod in `Running` state.

> `hpa-example` is the official K8s load-test image — a CPU-burning PHP app designed for autoscaling demos.

---

### 4. Expose via Service

```bash
kubectl apply -f service.yaml
kubectl get svc -n hpa-lab
```

Expected: `php-apache` with a `ClusterIP`. The DNS name `php-apache.hpa-lab.svc.cluster.local` is now resolvable inside the cluster via CoreDNS.

---

### 5. Create the HPA

```bash
kubectl apply -f hpa.yaml
kubectl get hpa -n hpa-lab
```

Expected:
```
NAME         REFERENCE               TARGETS       MINPODS   MAXPODS   REPLICAS   AGE
php-apache   Deployment/php-apache   cpu: 0%/50%   1         5         1          10s
```

**What 50% means:** Pod requests 200m CPU → threshold = 100m. Average CPU across all pods above 100m → HPA scales up.

---

### 6. Load Test — Trigger the HPA

```bash
kubectl run load-generator --image=busybox --restart=Never -n hpa-lab -- /bin/sh -c "while true; do wget -q -O- http://php-apache.hpa-lab.svc.cluster.local; done"
```

Watch HPA react in a second terminal:

```bash
kubectl get hpa -n hpa-lab -w
```

Expected progression:
```
cpu: 0%/50%    REPLICAS: 1
cpu: 143%/50%  REPLICAS: 1
cpu: 143%/50%  REPLICAS: 3
cpu: 89%/50%   REPLICAS: 5
```

Verify with:

```bash
kubectl top pod -n hpa-lab
```

---

### 7. Watch Scale Down

```bash
kubectl delete pod load-generator -n hpa-lab
kubectl get hpa -n hpa-lab -w
```

CPU drops to 0%. HPA waits **5 minutes** (stabilization window) before scaling replicas back to 1.

> This prevents flapping — rapid scale-up/scale-down cycles from brief traffic fluctuations.

---

### 8. KEDA — Event-Driven Autoscaling (Concept)

HPA scales on CPU/memory only. **KEDA** extends autoscaling to any external metric:

| Trigger | Example |
|---|---|
| Queue depth | Azure Service Bus, RabbitMQ |
| HTTP request rate | NGINX, Prometheus |
| Custom metrics | Datadog, CloudWatch |

Key difference: KEDA can scale to **zero**. HPA minimum is 1.

No hands-on required — concept is sufficient for Senior DevOps interviews.

---

### 9. Cleanup

```bash
kubectl delete -f hpa.yaml
kubectl delete -f service.yaml
kubectl delete -f deployment.yaml
kubectl delete -f namespace.yaml
kind delete cluster --name k8s-labs
```

---

## Mastery Check

You have completed this lab if you can answer without reference:

1. What is Metrics Server and why does HPA depend on it?
2. What does `averageUtilization: 50` actually mean in terms of millicores?
3. What is the scale-down stabilization window and why does it exist?
4. What is the difference between HPA and KEDA?
5. What happens to HPA if Metrics Server goes down?
6. How does HPA know which Deployment to target?
7. What DNS name does a pod use to reach a Service, and what resolves it?
8. Why does HPA stop at `maxReplicas` even when CPU is still above threshold?

---

## What's Next

**Hands-On 9 — Lock It Down**

RBAC, ServiceAccounts, Roles, ClusterRoles, and Workload Identity. Control exactly who and what can talk to your cluster.