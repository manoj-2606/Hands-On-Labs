# Hands-On 3 — Make Your App Discoverable

## What This Lab Is About

Kubernetes pods are ephemeral. They die and respawn with new IPs constantly. You can never hardcode a Pod IP. A **Service** gives you a stable network endpoint that always routes to the right pod — no matter how many times it dies and respawns.

This lab teaches the foundational truth: **without a Service, your app is unreachable and your pod IPs are worthless.**

---

## Concepts Covered

- Services — stable network endpoint in front of ephemeral pods
- ClusterIP — internal-only Service, foundation of all Service types
- NodePort — exposes app on a node port, builds on top of ClusterIP
- LoadBalancer — cloud LB in front of NodePort, production standard
- Endpoints — the dynamic list of pod IPs behind a Service
- CoreDNS — Kubernetes internal DNS, resolves service names to ClusterIPs
- kube-proxy — writes iptables rules on every node so Service IPs actually route traffic

---

## Prerequisites

- kind cluster running (`kind create cluster --name k8s-labs`)
- kubectl installed
- Docker running
- Hands-On 1 and 2 completed

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
| `deployment.yaml` | Deploys 3 nginx replicas with label `app: my-app` |
| `service-clusterip.yaml` | ClusterIP Service — internal only |
| `service-nodeport.yaml` | NodePort Service — exposes app on node port 30080 |
| `service-loadbalancer.yaml` | LoadBalancer Service — production standard |

---

## Step-by-Step

### 1. Create Namespace

```bash
kubectl apply -f namespace-team-a.yaml
kubectl get namespaces
```

Expected: `team-a` appears in the list.

---

### 2. Deploy the App

```bash
kubectl apply -f deployment.yaml
kubectl get pods -n team-a
```

Expected: 3 pods in `Running` state with label `app: my-app`.

---

### 3. Create ClusterIP Service

```bash
kubectl apply -f service-clusterip.yaml
kubectl get svc -n team-a
```

Expected: Service with `TYPE: ClusterIP` and a stable `CLUSTER-IP` assigned. No `EXTERNAL-IP`.

**Key fields:**
- `selector: app: my-app` — matches pod labels, ties Service to pods
- `port: 80` — what callers use to reach the Service
- `targetPort: 80` — what the container actually listens on

> In production, `port` and `targetPort` are often different. Example: caller hits `service:8080`, container listens on `3000`.

---

### 4. Test ClusterIP Routing

ClusterIP is internal-only. Must test from inside the cluster.

```bash
kubectl run test-pod --image=busybox --restart=Never -n team-a -- sleep 3600

# Hit the service by name — CoreDNS resolves it
kubectl exec -it test-pod -n team-a -- wget -qO- http://my-app-service:80

# Observe DNS resolution
kubectl exec -it test-pod -n team-a -- nslookup my-app-service
```

Expected:
- `wget` returns nginx HTML
- `nslookup` returns `my-app-service.team-a.svc.cluster.local → 10.96.x.x`

---

### 5. Observe Endpoints

Endpoints = the actual pod IPs behind a Service. Updated dynamically as pods die and respawn.

```bash
kubectl get endpoints -n team-a

# Verify endpoints match pod IPs
kubectl get pods -n team-a -o wide

# Kill a pod and watch endpoints update
kubectl delete pod <pod-name> -n team-a
kubectl get endpoints -n team-a -w
```

Expected: One IP drops, new pod spawns, new IP appears in Endpoints automatically. Service IP never changes.

---

### 6. Create NodePort Service

```bash
kubectl apply -f service-nodeport.yaml
kubectl get svc -n team-a
```

Expected: Service with `TYPE: NodePort`, port shown as `80:30080/TCP`.

**Test from inside the cluster (kind limitation — node IP not reachable from host):**

```bash
kubectl port-forward svc/my-app-nodeport 30080:80 -n team-a
```

Open browser: `http://localhost:30080`

Expected: nginx welcome page.

> In real AKS/EKS/GKE, you hit `<node-ip>:30080` directly from outside. kind runs inside Docker so node IP is not accessible from Windows host.

---

### 7. Create LoadBalancer Service

```bash
kubectl apply -f service-loadbalancer.yaml
kubectl get svc -n team-a -w
```

Expected: `EXTERNAL-IP` stays `<pending>` in kind — no cloud provider to provision a real IP.

On AKS this would be a real Azure public IP within 30–60 seconds:
```
my-app-loadbalancer   LoadBalancer   10.96.x.x   20.86.142.10   80:30709/TCP
```

**The full production chain:**
```
Internet → Azure Public IP (LoadBalancer) → Node:30709 (NodePort) → ClusterIP → Pod
```

All three Service types exist simultaneously. LoadBalancer sits on top — it doesn't replace the others.

---

### 8. CoreDNS — Cross-Namespace DNS

CoreDNS runs as 2 pods in `kube-system` (HA). Every pod in the cluster uses it as DNS resolver automatically.

```bash
kubectl get pods -n kube-system
```

**Test cross-namespace DNS resolution:**

```bash
kubectl create namespace team-b
kubectl run test-cross --image=busybox --restart=Never -n team-b -- sleep 3600

# Short name — FAILS from different namespace
kubectl exec -it test-cross -n team-b -- wget -qO- http://my-app-service

# Full DNS name — WORKS from any namespace
kubectl exec -it test-cross -n team-b -- wget -qO- http://my-app-service.team-a.svc.cluster.local
```

**DNS format:**
```
<service-name>.<namespace>.svc.cluster.local
```

> Production rule: never hardcode IPs. Always use service names. For cross-namespace calls, always use the full DNS name.

---

### 9. Cleanup

```bash
kubectl delete namespace team-a
kubectl delete namespace team-b
kind delete cluster --name k8s-labs
```

---

## Service Types — Summary

| Type | Reachable From | Use Case |
|---|---|---|
| ClusterIP | Inside cluster only | Internal service-to-service communication |
| NodePort | Outside cluster via node IP | Dev/testing only, not production |
| LoadBalancer | Internet via cloud LB public IP | Production external traffic |

## The Full Traffic Chain (Production)

```
Internet
  → Azure Load Balancer (public IP)
  → Node IP : NodePort (auto-created)
  → ClusterIP (stable virtual IP)
  → Endpoints (dynamic pod IPs)
  → Pod
```

## CoreDNS Resolution Chain

```
Pod calls → http://my-app-service
  → CoreDNS expands → my-app-service.team-a.svc.cluster.local
  → Returns ClusterIP → 10.96.x.x
  → kube-proxy iptables routes → real pod IP
  → Pod responds
```

---

## Mastery Check

Answer without reference:

1. Why can't you hardcode a pod IP to call another service?
2. What is the difference between `port` and `targetPort` in a Service?
3. Why does ClusterIP traffic actually reach a pod if the IP is virtual?
4. What happens to Endpoints when a pod dies?
5. Why does a short service name fail cross-namespace but full DNS works?
6. Why does LoadBalancer type also create a NodePort automatically?
7. What is CoreDNS and where does it run?
8. Why are there 2 CoreDNS pods?

---

## What's Next

**Hands-On 4 — Config Without Chaos**

Manage configuration and secrets without hardcoding values. ConfigMaps, Secrets, Volume Mounts, and Workload Identity.