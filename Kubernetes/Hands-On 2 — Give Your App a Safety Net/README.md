# Hands-On 2 — Give Your App a Safety Net

## Why This Lab

In Hands-On 1, you killed a raw Pod — it stayed dead. No one came to rescue it.  
In Hands-On 2, you give your app a **controller** — a Deployment. Now when a Pod dies, the cluster brings it back automatically. You also learn how to update your app version with zero downtime and roll it back instantly when something goes wrong.

This is the foundation of how every production workload runs in Kubernetes.

---

## What You'll Learn

- The **Deployment → ReplicaSet → Pod** ownership chain
- **Reconciliation in action** — delete a Pod, watch it resurrect
- **Rolling Update** — update image version with zero downtime
- **Rollback** — revert a bad deployment in one command
- **Resource Limits** — CPU/memory boundaries and what happens when you breach them

---

## Key Concepts Before You Start

### Deployment → ReplicaSet → Pod Chain
A Deployment does not manage Pods directly. It creates a **ReplicaSet**, which manages the Pods. The Deployment manages the ReplicaSets.

```
Deployment
  └── ReplicaSet (v1 — nginx:1.25)   ← active
        ├── Pod 1
        └── Pod 2
  └── ReplicaSet (v0 — old version)  ← scaled to 0, kept for rollback
```

### Reconciliation Loop
The ReplicaSet controller constantly watches: `desired replicas vs actual replicas`.  
If a Pod dies → `desired=2, actual=1` → new Pod spins up immediately. You don't do anything.

### selector.matchLabels
This is the **ownership contract** between the ReplicaSet and its Pods.  
Any Pod in the namespace with the matching label is claimed by the ReplicaSet.  
`selector.matchLabels` must always match `template.metadata.labels` — K8s rejects it otherwise.

### Resource Requests vs Limits
| Field | Meaning |
|---|---|
| `requests.cpu` | Guaranteed CPU the scheduler reserves on the node |
| `requests.memory` | Guaranteed memory reserved on the node |
| `limits.cpu` | Hard ceiling — breach it → Pod gets throttled |
| `limits.memory` | Hard ceiling — breach it → Pod gets **OOMKilled** (killed immediately) |

Unit reference: `100m` = 100 millicores (0.1 CPU core). `64Mi` = 64 Mebibytes.

---

## Prerequisites

- kind cluster running (`kind create cluster --name k8s-labs`)
- kubectl configured
- Docker running

---

## Files in This Lab

| File | Purpose |
|---|---|
| `namespace-team-a.yaml` | Creates namespace `team-a` + Deployment with 2 replicas of nginx:1.25 |

---

## Step-by-Step

### Step 1 — Deploy the App

Apply the manifest:

```bash
kubectl apply -f namespace-team-a.yaml
kubectl get pods -n team-a
```

Expected output — wait until both pods show `Running`:

```
NAME                          READY   STATUS    RESTARTS   AGE
app-team-a-856f994596-27rr6   1/1     Running   0          1m
app-team-a-856f994596-w6b6d   1/1     Running   0          1m
```

Notice the pod names: `<deployment>-<replicaset-hash>-<pod-hash>`. Names are auto-generated — this is by design. Pods are ephemeral and interchangeable in a Deployment.

---

### Step 2 — Kill a Pod, Watch Reconciliation

Delete one Pod manually:

```bash
kubectl delete pod <pod-name> -n team-a
kubectl get pods -n team-a -w
```

Replace `<pod-name>` with one of the running pod names from Step 1.

What you'll see:
- The deleted pod disappears
- A **new pod with a different name** appears within seconds
- ReplicaSet detected `desired=2, actual=1` and self-healed immediately

This is the core lesson. A raw Pod (Lab 1) stays dead. A Deployment-managed Pod is resurrected automatically.

---

### Step 3 — Rolling Update (Zero Downtime)

Update the nginx image from `1.25` to `1.26`:

```bash
kubectl set image deployment/app-team-a app-team-a=nginx:1.26 -n team-a
kubectl rollout status deployment/app-team-a -n team-a
kubectl get pods -n team-a -w
```

What you'll see in rollout status:
```
Waiting for deployment: 1 out of 2 new replicas have been updated...
Waiting for deployment: 1 old replicas are pending termination...
deployment "app-team-a" successfully rolled out
```

What's happening under the hood:
- K8s creates a **brand new ReplicaSet** for nginx:1.26
- Spins up 1 new Pod → waits for it to be Ready → terminates 1 old Pod
- Repeats until all Pods are on the new version
- At no point are both old Pods dead — **app stays alive throughout**

Check both ReplicaSets:

```bash
kubectl get replicasets -n team-a
```

You'll see the old ReplicaSet scaled to 0 but still present — kept for rollback.

> **Production rule:** Always update the image in your YAML file and use `kubectl apply -f`.  
> Never mix `kubectl set image` (imperative) with `kubectl apply` (declarative) on the same resource.

---

### Step 4 — Rollback

Simulate a bad deployment by rolling back to the previous version:

```bash
kubectl rollout undo deployment/app-team-a -n team-a
kubectl get replicasets -n team-a
```

What you'll see:
```
NAME                    DESIRED   CURRENT   READY
app-team-a-74b8b74675   0         0         0      ← nginx:1.26 scaled down
app-team-a-856f994596   2         2         2      ← nginx:1.25 back up
```

No rebuild. No redeploy. K8s simply scaled the old ReplicaSet back up and scaled the new one down — instant pointer swap.

---

### Cleanup

```bash
kubectl delete namespace team-a
kind delete cluster --name k8s-labs
```

---

## What's Next

**Hands-On 3 — Make Your App Discoverable**

Pods have dynamic IPs that change every time they restart. Services give your app a stable network identity. You'll learn ClusterIP, CoreDNS, Endpoints, and kube-proxy.