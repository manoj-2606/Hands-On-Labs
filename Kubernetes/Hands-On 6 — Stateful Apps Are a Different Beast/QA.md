# Hands-On 6 — Mastery Check

Answer these without reference. Answers are below each question.

---

**Q1. Why does a StatefulSet pod come back with the same name after deletion?**

StatefulSet assigns pods ordinal-based names (myapp-0, myapp-1, myapp-2). The StatefulSet controller — not the scheduler — is responsible for maintaining this identity. When a pod dies, the controller creates a replacement with the exact same name and ordinal. The pod name is not random — it is deterministic by design.

A Deployment's ReplicaSet creates a replacement pod with a new random suffix. It has no concept of identity — only count.

---

**Q2. What does `clusterIP: None` do to DNS behavior?**

It creates a Headless Service. Without `clusterIP: None`, a Service gets a stable virtual IP (ClusterIP) and kube-proxy load balances traffic across pod IPs behind the scenes.

With `clusterIP: None`:
- No virtual IP is assigned
- No load balancing occurs
- DNS returns the individual pod IPs directly
- Each pod gets its own DNS entry: `pod-name.service-name.namespace.svc.cluster.local`

This is essential for stateful workloads where clients need to reach a specific pod (e.g., primary DB replica), not a random one.

---

**Q3. Why does each pod get its own PVC instead of sharing one?**

`volumeClaimTemplates` in a StatefulSet creates a unique PVC per pod at creation time — `data-myapp-0`, `data-myapp-1`, `data-myapp-2`. Each PVC binds to a separate PV (separate disk).

If pods shared a PVC (`ReadWriteOnce` mode), only one pod could mount it at a time — and even with `ReadWriteMany`, concurrent writes from multiple pods would corrupt stateful data (database files, write-ahead logs, etc.).

Separate PVCs = separate disks = isolated state per pod. This is the storage guarantee that makes StatefulSets safe for databases.

---

**Q4. What does an Init Container guarantee before the main container starts?**

An Init Container runs to completion (exit code 0) before any container in the pod starts. The main container is blocked until all Init Containers succeed in order.

Guarantees:
- Filesystem is pre-populated before the app boots
- Dependencies are verified before the app starts
- One-time setup tasks (schema migrations, config writes) complete first

If an Init Container fails, it retries according to the pod's restart policy. The main container never starts until every Init Container exits 0.

In this lab: the Init Container writes `identity.txt` to the shared volume before the main container reads it.

---

**Q5. Why aren't PVCs deleted when you delete a StatefulSet?**

By design. Kubernetes treats PVCs as independent resources — they are not owned by the StatefulSet. The StatefulSet controller deliberately does not cascade-delete PVCs on deletion.

Reason: data safety. Accidentally deleting a StatefulSet (misconfigured CI pipeline, human error) should not destroy production database volumes. You must explicitly delete PVCs with `kubectl delete pvc`.

The ReclaimPolicy on the StorageClass determines what happens to the PV after the PVC is deleted:
- `Delete` (kind default) → PV and underlying disk are removed
- `Retain` (production default) → PV stays, disk survives, must be manually reclaimed

---

**Q6. What is the DNS format to reach a specific pod in a StatefulSet?**

```
<pod-name>.<service-name>.<namespace>.svc.cluster.local
```

Example from this lab:
```
myapp-1.myapp.stateful-lab.svc.cluster.local
```

Requirements for this to work:
- Service must be Headless (`clusterIP: None`)
- `serviceName` in the StatefulSet spec must match the Service name
- Pod must be Running and Ready

Without a Headless Service, per-pod DNS does not exist — only the service-level DNS resolves, and it routes to a random pod.

---

**Q7. What is the difference between a StatefulSet and a Deployment in terms of pod identity and storage?**

| | Deployment | StatefulSet |
|---|---|---|
| Pod names | Random hash suffix (`app-7d9f4b-xkqzp`) | Ordinal suffix (`app-0`, `app-1`) |
| Pod identity | None — interchangeable | Stable — each pod has a fixed identity |
| Storage | Shared volume or no persistence | Unique PVC per pod via volumeClaimTemplates |
| Startup order | Parallel | Sequential (0 → 1 → 2) |
| Shutdown order | Parallel | Reverse sequential (2 → 1 → 0) |
| DNS per pod | No | Yes — via Headless Service |
| Use case | Stateless apps | Databases, queues, caches |

---

**Q8. A pod in a StatefulSet is stuck in `Pending`. What are the likely causes?**

1. **PVC not bound** — StorageClass provisioner failed, no available PV, or `WaitForFirstConsumer` is waiting for pod scheduling
2. **Previous pod not yet Running** — StatefulSet starts pods sequentially; pod-1 won't start until pod-0 is Running and Ready
3. **Insufficient node resources** — not enough CPU/memory on any schedulable node
4. **Taints/tolerations mismatch** — node has a taint the pod doesn't tolerate

Diagnose with:
```bash
kubectl describe pod myapp-1 -n stateful-lab
# Check Events section — scheduler will explain why it's stuck

kubectl get pvc -n stateful-lab
# Check if PVC is Pending instead of Bound
```