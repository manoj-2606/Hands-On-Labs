# Hands-On 1 — The Cluster is a Living Organism

## What This Lab Is About

Kubernetes is a **reconciliation engine**. You declare what you want. It constantly watches and tries to match reality to your declaration. You are not giving commands — you are making promises to the control plane.

This lab teaches you the foundational truth: **without a controller, a dead Pod stays dead.**

---

## Concepts Covered

- Pods — the smallest deployable unit
- Namespaces — logical isolation between teams/environments
- Labels + Selectors — how Kubernetes finds and groups resources
- Reconciliation Loop — the control plane's heartbeat
- `kubectl describe` — reading the event chain for debugging

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
| `namespace-team-a.yaml` | Creates namespace `team-a` |
| `namespace-team-b.yaml` | Creates namespace `team-b` |
| `pod-team-a.yaml` | Raw Pod in `team-a` with labels `env=prod`, `team=a`, `version=v1` |
| `pod-team-b.yaml` | Raw Pod in `team-b` with labels `env=prod`, `team=b`, `version=v1` |
| `pod-broken.yaml` | Pod with invalid image tag — triggers `ImagePullBackOff` |

---

## Step-by-Step

### 1. Create Namespaces

```bash
kubectl apply -f namespace-team-a.yaml
kubectl apply -f namespace-team-b.yaml
kubectl get namespaces
```

You will see `team-a` and `team-b` alongside system namespaces.

**System namespaces explained:**
- `default` — where resources land if no namespace is specified
- `kube-system` — core K8s components: CoreDNS, kube-proxy, CNI
- `kube-public` — readable by everyone, rarely used
- `kube-node-lease` — node heartbeat tracking
- `local-path-storage` — kind-specific default StorageClass

---

### 2. Deploy Raw Pods

```bash
kubectl apply -f pod-team-a.yaml
kubectl apply -f pod-team-b.yaml
kubectl get pods -n team-a
kubectl get pods -n team-b
```

---

### 3. Query by Label Across Namespaces

```bash
kubectl get pods -l env=prod --all-namespaces
```

Both pods returned with one command — this is labels in action. Kubernetes uses labels as the universal glue between resources.

---

### 4. The Pain Exercise — Kill a Raw Pod

```bash
kubectl delete pod pod-team-a -n team-a
kubectl get pods -n team-a
```

**Expected:** `No resources found in team-a namespace.`

**Why:** A raw Pod has no controller watching over it. No ReplicaSet. No Deployment. Dead = dead. This is the core lesson of Hands-On 1. Hands-On 2 fixes this with Deployments.

---

### 5. The Broken Image Exercise

```bash
kubectl apply -f pod-broken.yaml
kubectl get pods -n team-a -w
```

Watch the status cycle:
```
NAME         READY   STATUS             RESTARTS   AGE
pod-broken   0/1     ErrImagePull       0          10s
pod-broken   0/1     ImagePullBackOff   0          25s
```

- `ErrImagePull` — Kubernetes tried to pull the image, registry returned `not found`
- `ImagePullBackOff` — K8s backing off with exponential delay before retrying

Press `Ctrl+C` to stop watching.

---

### 6. Read the Event Chain

```bash
kubectl describe pod pod-broken -n team-a
```

Scroll to the **Events** section. This is the most important debugging skill in Kubernetes. The event chain tells you exactly what the control plane attempted and where it failed.

Key fields to read:
- `Status` — current Pod state
- `State: Waiting / Reason: ImagePullBackOff` — container never started
- `Events` — chronological trail of what happened

---

### 7. Cleanup

```bash
kubectl delete pod pod-broken -n team-a
kubectl delete pod pod-team-b -n team-b
kubectl delete namespace team-a
kubectl delete namespace team-b
kind delete cluster --name k8s-labs
```

---

## Mastery Check

You have completed this lab if you can answer without reference:

1. Why does a raw Pod not restart when deleted?
2. What is the difference between `ErrImagePull` and `ImagePullBackOff`?
3. How do you query pods across all namespaces filtered by a label?
4. What does the Events section in `kubectl describe` tell you?
5. What is the reconciliation loop?

---

## What's Next

**Hands-On 2 — Give Your App a Safety Net**

Deploy the same app using a Deployment. Kill a Pod. Watch it resurrect in seconds. Understand the Deployment → ReplicaSet → Pod ownership chain.