# Hands-On 6 — Stateful Apps Are a Different Beast

## What This Lab Is About

Deployments treat every Pod as disposable. **Stateful apps can't afford that.**

Databases, message queues, and caches need:
- **Stable identity** — pod-0, pod-1, not random hashes
- **Persistent storage** — data survives pod death
- **Ordered startup and shutdown**

StatefulSets deliver all three. This lab proves each guarantee hands-on — you will kill pods, inspect DNS, and watch storage survive.

---

## Concepts Covered

| Concept | Why It Matters |
|---|---|
| StatefulSet | Controller for stateful workloads — ordered, stable identity |
| PVC (PersistentVolumeClaim) | Pod's request for storage |
| PV (PersistentVolume) | Actual storage backing the claim |
| StorageClass | Dynamic provisioner — creates PV on demand |
| Headless Service | DNS per pod, no load balancing, no virtual IP |
| Init Containers | Run-to-completion before main container starts |
| volumeClaimTemplates | Each pod gets its own PVC — not shared |

---

## Mental Model

```
StatefulSet
  └── myapp-0  →  PVC: data-myapp-0  →  PV (actual disk)
  └── myapp-1  →  PVC: data-myapp-1  →  PV (actual disk)
  └── myapp-2  →  PVC: data-myapp-2  →  PV (actual disk)

Headless Service → DNS: myapp-0.myapp.stateful-lab.svc.cluster.local
```

Kill myapp-0 → comes back as **myapp-0**, reattaches the **same PVC**. A Deployment can never guarantee this.

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
kubectl get storageclass
```

Expected StorageClass output:
```
NAME                 PROVISIONER             RECLAIMPOLICY   VOLUMEBINDINGMODE
standard (default)   rancher.io/local-path   Delete          WaitForFirstConsumer
```

---

## Files in This Lab

| File | Purpose |
|---|---|
| `namespace-stateful.yaml` | Creates namespace `stateful-lab` |
| `headless-service.yaml` | Headless Service — `clusterIP: None`, per-pod DNS |
| `statefulset.yaml` | 3-replica StatefulSet with Init Container + volumeClaimTemplates |

---

## Step-by-Step

### 1. Create Namespace

```bash
kubectl apply -f namespace-stateful.yaml
kubectl get namespace stateful-lab
```

---

### 2. Deploy Headless Service + StatefulSet

```bash
kubectl apply -f headless-service.yaml
kubectl apply -f statefulset.yaml
```

Watch sequential pod startup:

```bash
kubectl get pods -n stateful-lab -w
```

Expected — pods start one at a time, never in parallel:
```
myapp-0   Init:0/1 → PodInitializing → Running
myapp-1   Init:0/1 → PodInitializing → Running   (only after myapp-0 is Running)
myapp-2   Init:0/1 → PodInitializing → Running   (only after myapp-1 is Running)
```

Verify each pod has its own PVC:

```bash
kubectl get pvc -n stateful-lab
```

Expected:
```
NAME           STATUS   VOLUME         CAPACITY   ACCESS MODES
data-myapp-0   Bound    pvc-xxx...     100Mi      RWO
data-myapp-1   Bound    pvc-yyy...     100Mi      RWO
data-myapp-2   Bound    pvc-zzz...     100Mi      RWO
```

---

### 3. The Pain Exercise — Kill a Pod, Prove Nothing Is Lost

Read the identity file written by the Init Container:

```bash
kubectl exec myapp-0 -n stateful-lab -- cat /data/identity.txt
```

Delete the pod:

```bash
kubectl delete pod myapp-0 -n stateful-lab
kubectl get pods -n stateful-lab -w
```

Once Running again, verify data survived:

```bash
kubectl exec myapp-0 -n stateful-lab -- cat /data/identity.txt
kubectl get pvc -n stateful-lab
```

The VOLUME ID of `data-myapp-0` must be identical before and after deletion.

---

### 4. Prove Headless DNS

Resolve the service — returns all pod IPs, no virtual IP:

```bash
kubectl exec myapp-0 -n stateful-lab -- nslookup myapp.stateful-lab.svc.cluster.local
```

Resolve a specific pod by stable DNS:

```bash
kubectl exec myapp-0 -n stateful-lab -- nslookup myapp-1.myapp.stateful-lab.svc.cluster.local
```

Cross-check the IP:

```bash
kubectl get pod myapp-1 -n stateful-lab -o wide
```

DNS IP must match pod IP exactly.

---

### 5. Cleanup

```bash
kubectl delete statefulset myapp -n stateful-lab
kubectl delete service myapp -n stateful-lab

# PVCs survive StatefulSet deletion — delete manually
kubectl delete pvc data-myapp-0 data-myapp-1 data-myapp-2 -n stateful-lab
kubectl delete namespace stateful-lab
kind delete cluster --name k8s-labs
```

---

## Mastery Check

Answer without reference:

1. Why does a StatefulSet pod come back with the same name after deletion?
2. What does `clusterIP: None` do to DNS behavior?
3. Why does each pod get its own PVC instead of sharing one?
4. What does an Init Container guarantee before the main container starts?
5. Why aren't PVCs deleted when you delete a StatefulSet?
6. What is the DNS format to reach a specific pod in a StatefulSet?

---

## What's Next

**Hands-On 7 — One Pod Per Node, No Exceptions**

DaemonSets, Taints, Tolerations, Node Affinity, Pod Anti-Affinity.