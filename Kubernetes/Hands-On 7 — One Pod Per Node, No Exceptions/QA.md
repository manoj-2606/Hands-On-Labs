# Hands-On 7 — Mastery Check

Answer these without reference. Answers are below each question.

---

**Q1. What is a DaemonSet and when do you use it instead of a Deployment?**

A DaemonSet ensures exactly one pod runs on every eligible node in the cluster. Node count drives pod count — there is no `replicas` field. When a new node joins, the DaemonSet controller automatically schedules a pod on it. When a node is removed, the pod is cleaned up.

Use a DaemonSet when the workload must run on every node — log collectors (Fluentd), monitoring agents (Prometheus node-exporter), network plugins (CNI), security scanners, storage daemons.

Use a Deployment when you need a specific number of replicas distributed across nodes without caring which nodes they land on.

---

**Q2. What are the three taint effects and what does each do?**

| Effect | Behavior |
|---|---|
| `NoSchedule` | New pods are not scheduled on this node. Existing pods are unaffected. |
| `PreferNoSchedule` | Scheduler tries to avoid this node but will use it if no other option exists. Soft rule. |
| `NoExecute` | New pods are blocked AND existing pods without a matching toleration are evicted immediately. |

`NoExecute` is the most aggressive — it affects both running and future pods.

---

**Q3. What is the difference between a Taint and a Toleration?**

Taint is on the node. Toleration is on the pod.

- Taint = the node saying "stay away unless you accept this condition"
- Toleration = the pod saying "I accept that condition, allow me in"

They work as a pair. A taint without a matching toleration blocks the pod. A toleration without a matching taint is harmless — the pod just carries a key that opens no lock on that node.

---

**Q4. What is the difference between `requiredDuringScheduling` and `preferredDuringScheduling`?**

`requiredDuringScheduling` = hard rule. The pod will only be scheduled on a node that matches the affinity rule. If no matching node exists, the pod stays Pending indefinitely.

`preferredDuringScheduling` = soft rule. The scheduler tries to find a matching node but will schedule the pod elsewhere if no match is found. Pod never stays Pending because of this rule alone.

Use `required` when placement correctness is critical (e.g., GPU workloads must land on GPU nodes).
Use `preferred` when you want best-effort placement without risking availability.

---

**Q5. What does `IgnoredDuringExecution` mean?**

The affinity rule is only evaluated at scheduling time — when the pod is first being placed. Once the pod is running, the rule is ignored.

If the node's label changes after the pod is scheduled there, the pod is not evicted. It keeps running regardless.

The opposite (`RequiredDuringExecution`) would evict the pod if the node no longer satisfies the rule — but this is not yet available in stable Kubernetes.

---

**Q6. Why does a third replica stay Pending with Pod Anti-Affinity on a 2-node cluster?**

The anti-affinity rule says: "Don't schedule me on a node where a pod with label `app=spread-app` already exists."

With 2 nodes:
- Pod 1 → lands on worker
- Pod 2 → worker is occupied, goes to worker2
- Pod 3 → worker is occupied, worker2 is occupied, no third node → Pending

Anti-affinity with `requiredDuringScheduling` is a hard rule. The scheduler will not violate it. The pod waits until a new node joins the cluster.

---

**Q7. What is `topologyKey` and why does it matter in Pod Anti-Affinity?**

`topologyKey` defines the boundary within which the anti-affinity rule is enforced.

`kubernetes.io/hostname` = each node is its own topology zone. No two matching pods on the same node.

If you used `topology.kubernetes.io/zone` instead, the rule would enforce one pod per cloud availability zone — multiple nodes in the same zone would still count as one boundary.

Without `topologyKey`, the anti-affinity rule has no scope — Kubernetes requires it to be set.

---

**Q8. Why does the control-plane node not get a DaemonSet pod by default?**

kubeadm automatically applies this taint to the control-plane node during cluster initialization:

```
node-role.kubernetes.io/control-plane:NoSchedule
```

DaemonSet pods without a matching toleration are blocked from scheduling there. This protects the cluster brain — API server, etcd, scheduler, controller-manager — from being starved of resources by workload pods.

To run a DaemonSet pod on the control-plane, add this toleration:

```yaml
tolerations:
  - key: "node-role.kubernetes.io/control-plane"
    operator: "Exists"
    effect: "NoSchedule"
```