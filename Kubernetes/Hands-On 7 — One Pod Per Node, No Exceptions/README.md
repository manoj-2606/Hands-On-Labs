# Hands-On 7 — One Pod Per Node, No Exceptions

## What This Lab Is About

Some workloads must run on every node — log collectors, monitoring agents, network plugins, security scanners. A Deployment can't guarantee this. It only manages replica count, not placement per node.

DaemonSets guarantee exactly one pod per node. New node joins → pod appears automatically. Node removed → pod gone automatically. No manual intervention.

This lab also covers how to control scheduling using Taints, Tolerations, and Affinity rules.

---

## Concepts Covered

| Concept | Why It Matters |
|---|---|
| DaemonSet | One pod per node — auto-managed, no replicas field |
| Taints | Node repels pods — "stay away unless you tolerate this" |
| Tolerations | Pod accepts a taint — "I can run on that node" |
| Node Affinity | Pod chooses which nodes it lands on by label |
| Pod Anti-Affinity | Pod avoids nodes where a matching pod already exists |

---

## Mental Model

```
Taints/Tolerations  = Node pushes pods away. Pod carries a key to get in.
Node Affinity       = Pod pulls itself toward specific nodes by label.
Pod Anti-Affinity   = Pod avoids nodes where its siblings already exist.
```

---

## Prerequisites

- kind installed
- kubectl installed
- Docker running

---

## Cluster Setup

```yaml
# kind-config.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
  - role: worker
  - role: worker
```

```bash
kind create cluster --name k8s-labs --config kind-config.yaml
kubectl get nodes
```

Expected:
```
NAME                     STATUS   ROLES           AGE   VERSION
k8s-labs-control-plane   Ready    control-plane   Xs    v1.x.x
k8s-labs-worker          Ready    <none>          Xs    v1.x.x
k8s-labs-worker2         Ready    <none>          Xs    v1.x.x
```

---

## Files in This Lab

| File | Purpose |
|---|---|
| `kind-config.yaml` | Multi-node kind cluster — 1 control-plane, 2 workers |
| `namespace-daemonset.yaml` | Creates namespace `daemon-lab` |
| `daemonset.yaml` | DaemonSet — one pod per eligible node |
| `pod-affinity.yaml` | Pod with required Node Affinity — zone=a only |
| `pod-anti-affinity.yaml` | Deployment with Pod Anti-Affinity — one per node enforced |

---

## Step-by-Step

### 1. Create Namespace

```bash
kubectl apply -f namespace-daemonset.yaml
kubectl get namespace daemon-lab
```

---

### 2. Deploy DaemonSet

```bash
kubectl apply -f daemonset.yaml
kubectl get pods -n daemon-lab -o wide
```

Expected — one pod per worker, control-plane skipped:
```
NAME                  READY   STATUS    NODE
log-collector-xxxx    1/1     Running   k8s-labs-worker
log-collector-yyyy    1/1     Running   k8s-labs-worker2
```

Control-plane is skipped because kubeadm applies this taint by default:
```
node-role.kubernetes.io/control-plane:NoSchedule
```

---

### 3. Taint a Node — Evict the Pod

```bash
kubectl taint node k8s-labs-worker2 env=production:NoExecute
kubectl get pods -n daemon-lab -o wide -w
```

`NoExecute` evicts existing pods immediately and blocks new ones.

Expected — worker2 pod terminated:
```
NAME                  READY   STATUS        NODE
log-collector-xxxx    1/1     Terminating   k8s-labs-worker2
log-collector-yyyy    1/1     Running       k8s-labs-worker
```

---

### 4. Add Toleration — Pod Comes Back

Add `tolerations` to `daemonset.yaml`:

```yaml
tolerations:
  - key: "env"
    operator: "Equal"
    value: "production"
    effect: "NoExecute"
```

```bash
kubectl apply -f daemonset.yaml
kubectl get pods -n daemon-lab -o wide
```

Pod reschedules back onto worker2. The rolling update replaces pods on all nodes with the new spec.

---

### 5. Node Affinity — Pod Chooses Its Node

Label the nodes:

```bash
kubectl label node k8s-labs-worker zone=a
kubectl label node k8s-labs-worker2 zone=b
```

Deploy `pod-affinity.yaml` with `requiredDuringSchedulingIgnoredDuringExecution` for `zone=a`.

```bash
kubectl apply -f pod-affinity.yaml
kubectl get pod zone-a-pod -n daemon-lab -o wide
```

Expected — lands only on `k8s-labs-worker`:
```
NAME         READY   STATUS    NODE
zone-a-pod   1/1     Running   k8s-labs-worker
```

**Affinity types:**

| Type | Behavior |
|---|---|
| `requiredDuringScheduling` | Hard rule — pod stays Pending if no matching node |
| `preferredDuringScheduling` | Soft rule — tries to match, schedules anywhere if no match |

`IgnoredDuringExecution` = rule only applies at scheduling time. If node label changes after pod is running, pod is not evicted.

---

### 6. Pod Anti-Affinity — Enforce Spread

```bash
kubectl apply -f pod-anti-affinity.yaml
kubectl get pods -n daemon-lab -o wide
```

Expected — one pod per node, third replica stays Pending:
```
NAME             READY   STATUS    NODE
spread-app-xxx   1/1     Running   k8s-labs-worker
spread-app-yyy   1/1     Running   k8s-labs-worker2
spread-app-zzz   0/1     Pending   <none>
```

`topologyKey: kubernetes.io/hostname` = treat each node as a separate zone. No two `spread-app` pods on the same hostname.

---

### 7. Cleanup

```bash
kubectl delete namespace daemon-lab
kind delete cluster --name k8s-labs
```

---

## Mastery Check

1. What is a DaemonSet and when do you use it instead of a Deployment?
2. What are the three taint effects and what does each do?
3. What is the difference between a Taint and a Toleration?
4. What is the difference between `requiredDuringScheduling` and `preferredDuringScheduling`?
5. What does `IgnoredDuringExecution` mean?
6. Why does a third replica stay Pending with Pod Anti-Affinity on a 2-node cluster?
7. What is `topologyKey` and why does it matter in Pod Anti-Affinity?

---

## What's Next

**Hands-On 8 — Scale or Die**

HPA, Metrics Server, KEDA concept, Load Testing.