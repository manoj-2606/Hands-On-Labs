# Hands-On 5 — Keep Your App Alive and Ready

## What This Lab Is About

Kubernetes knows if a container is running. It does not know if your app is actually healthy. Probes are how you teach Kubernetes the difference between a running container and a functioning app.

> "A container that is Running is not the same as an app that is working."

---

## Concepts Covered

- Liveness Probe — detect stuck/deadlocked apps and restart them
- Readiness Probe — remove unhealthy pods from traffic without restarting
- Startup Probe — protect slow-starting apps from premature liveness kills
- OOMKilled — what happens when a container exceeds its memory limit
- CrashLoopBackOff — kubelet backoff behavior after repeated failures
- kubelet vs ReplicaSet — who restarts containers vs who reschedules pods

---

## Prerequisites

- kind cluster running (`kind create cluster --name k8s-labs`)
- kubectl installed
- Hands-On 1–4 completed

---

## Cluster Setup

```bash
kind create cluster --name k8s-labs
kubectl create namespace team-a
```

---

## Files in This Lab

| File | Purpose |
|---|---|
| `app-no-probes.yaml` | Pod with no probes — demonstrates silent failure |
| `app-liveness.yaml` | Pod with Liveness probe — restarts on failure |
| `app-readiness.yaml` | Pod with Readiness probe — removed from traffic on failure |
| `app-startup.yaml` | Pod with Startup + Liveness probe — protects slow-starting app |
| `app-oom.yaml` | Pod with tiny memory limit — triggers OOMKilled |

---

## Three Probes — Quick Reference

| Probe | Question it answers | Action on failure |
|---|---|---|
| Liveness | Is the app alive or stuck? | Kill container, restart it |
| Readiness | Is the app ready for traffic? | Remove from Service endpoints |
| Startup | Has the app finished starting? | Blocks liveness/readiness until pass |

---

## Step-by-Step

### 1. Deploy Without Probes — See the Problem

```bash
kubectl apply -f app-no-probes.yaml
kubectl get pod app-no-probes -n team-a
```

Exec in and simulate a hung app:
```bash
kubectl exec -it app-no-probes -n team-a -- sh
sleep 3600 &
exit
```

```bash
kubectl get pod app-no-probes -n team-a
```

**What you observe:** Status = `Running`. Kubernetes has no idea the app is stuck. No restart. No alert. Traffic would keep hitting a dead app.

This is the silent failure probes solve.

---

### 2. Liveness Probe

Liveness answers: "Is the app still functional?" If no → kill and restart.

```bash
kubectl apply -f app-liveness.yaml
kubectl get pod app-liveness -n team-a -w
```

**What you observe:** Pod starts, probe checks `/tmp/healthy` every 5s, file exists (created at startup) → probe passes → stable at 0 restarts.

Break it intentionally:
```bash
kubectl exec -it app-liveness -n team-a -- sh
rm /tmp/healthy
exit
```

```bash
kubectl get pod app-liveness -n team-a -w
```

**What you observe:** After 3 failures (15s) → container killed and restarted. RESTARTS climbs.

**Key lesson:** Every restart wipes the container filesystem. Always create the health signal in the startup command:
```yaml
command: ["sh", "-c", "touch /tmp/healthy && sleep 3600"]
```

**Probe parameters explained:**

| Parameter | Purpose |
|---|---|
| `initialDelaySeconds` | Wait N seconds after container starts before first probe |
| `periodSeconds` | Run probe every N seconds |
| `failureThreshold` | Kill container after N consecutive failures |
| `timeoutSeconds` | Probe must respond within N seconds or counts as failure |

**Probe types in production:**

| Type | Example |
|---|---|
| `exec` | Check if file/process exists |
| `httpGet` | Hit `/healthz`, expect HTTP 200 |
| `tcpSocket` | Check if port is accepting connections |

`httpGet` is what 90% of production apps use:
```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8080
  initialDelaySeconds: 10
  periodSeconds: 5
```

---

### 3. Readiness Probe

Readiness answers: "Is the app ready to receive traffic?" If no → remove from Service endpoints. Container is NOT restarted.

```bash
kubectl apply -f app-readiness.yaml
kubectl get pod app-readiness -n team-a -w
```

Break it:
```bash
kubectl exec -it app-readiness -n team-a -- sh
rm /tmp/ready
exit
```

```bash
kubectl get pod app-readiness -n team-a -w
```

**What you observe:**
```
1/1     Running   0    ← receiving traffic
0/1     Running   0    ← removed from endpoints, container alive
```

RESTARTS stays at 0 — container never killed. Pod just stops receiving traffic.

Restore:
```bash
kubectl exec -it app-readiness -n team-a -- sh
touch /tmp/ready
exit
```

**Where does traffic go during 0/1?**
To other healthy pods in the same Deployment. With 3 replicas:
```
Pod-1 → 1/1 ✅ receives traffic
Pod-2 → 0/1 ❌ removed from endpoints
Pod-3 → 1/1 ✅ receives traffic
```

Single pod → no other pod to take over → requests fail. Never run single replicas in production.

**Readiness + rolling updates:** New pods don't receive traffic until readiness passes. Old pods keep serving until new ones are ready. This is how zero-downtime deployments work.

---

### 4. Startup Probe

**The problem:** Slow-starting apps (JVM, ML models) take 30-60s to boot. Liveness fires too early → kills container → infinite restart loop.

Startup probe blocks liveness and readiness until it passes. Runs once at startup, never again.

```bash
kubectl apply -f app-startup.yaml
kubectl get pod app-startup -n team-a -w
```

**Sequence:**
```
0s  → container starts, sleep 20 begins
5s  → startup probe: cat /tmp/healthy → FAIL
10s → startup probe → FAIL
15s → startup probe → FAIL
20s → sleep done, touch /tmp/healthy executes
25s → startup probe → PASS ✅
    → startup probe stops forever
    → liveness takes over
    → READY flips to 1/1
```

**What you observe:** Pod stays `0/1` for ~20 seconds, flips to `1/1` with 0 restarts.

`failureThreshold: 10` + `periodSeconds: 5` = 50 second startup window.

---

### 5. OOMKilled

When a container exceeds its memory `limit`, the Linux kernel kills the process immediately. No warning. No graceful shutdown.

```bash
kubectl apply -f app-oom.yaml
kubectl get pod app-oom -n team-a -w
```

**What you observe:**
```
ContainerCreating
Running           ← starts
OOMKilled         ← kernel kills it, RAM exceeded
Running           ← kubelet restarts
OOMKilled         ← same thing
CrashLoopBackOff  ← kubelet backs off
```

**OOMKill only triggers on RAM exhaustion** — not disk. Writing to `/tmp` or `/dev/null` does not count against memory limits.

**CrashLoopBackOff:** kubelet applies exponential backoff before retrying:
```
10s → 20s → 40s → 80s → max 5min
```

**kubelet vs ReplicaSet:**

| | kubelet | ReplicaSet |
|---|---|---|
| Scope | Single node | Cluster-wide |
| Trigger | Container dies (OOMKill, crash, exit) | Pod missing from cluster |
| Action | Restarts container on same node | Reschedules pod on another node |
| OOMKill handled by | ✅ kubelet | ❌ not involved |
| Node failure handled by | ❌ kubelet is gone | ✅ ReplicaSet reschedules |

---

### 6. Cleanup

```bash
kubectl delete pod app-no-probes -n team-a
kubectl delete pod app-liveness -n team-a
kubectl delete pod app-readiness -n team-a
kubectl delete pod app-startup -n team-a
kubectl delete pod app-oom -n team-a
kubectl delete namespace team-a
kind delete cluster --name k8s-labs
```

---

## Mastery Check

See `QA.md`

---

## What's Next

**Hands-On 6 — Stateful Apps Are a Different Beast**

StatefulSets, PVCs, StorageClass, Headless Services, Init Containers — when your app needs identity and persistent storage.