# Hands-On 2 — Mastery Check

Answer these without reference. If you can't, go back to the README.

---

**Q1. What is the Deployment → ReplicaSet → Pod ownership chain? Why does it exist as three layers instead of two?**

<details>
<summary>Answer</summary>

A Deployment manages ReplicaSets. A ReplicaSet manages Pods.  
Three layers exist because each layer has a distinct responsibility:
- **Deployment** — manages rollout strategy, update history, rollback
- **ReplicaSet** — maintains desired Pod count at any given version
- **Pod** — runs the actual container

When you do a rolling update, the Deployment creates a new ReplicaSet (new version) and scales it up while scaling the old ReplicaSet down. The old ReplicaSet is kept at 0 for rollback. You can't do this with two layers — you'd lose rollback history.

</details>

---

**Q2. You delete a Pod that is managed by a Deployment. What exactly happens, in order?**

<details>
<summary>Answer</summary>

1. Pod is deleted — actual replica count drops to 1
2. ReplicaSet controller detects `desired=2, actual=1`
3. ReplicaSet creates a new Pod spec
4. Scheduler assigns the Pod to a node
5. kubelet on that node pulls the image and starts the container
6. New Pod reaches Running state — count restored to 2

You did nothing. The reconciliation loop handled everything.

</details>

---

**Q3. What is `selector.matchLabels` and why must it match `template.metadata.labels`?**

<details>
<summary>Answer</summary>

`selector.matchLabels` is the ownership contract between the ReplicaSet and its Pods.  
The ReplicaSet uses this selector to find and claim Pods in the namespace.

It must match `template.metadata.labels` because the ReplicaSet creates Pods using the template — if the labels on the created Pods don't match the selector, the ReplicaSet can't find them and will keep creating more Pods indefinitely.

Kubernetes rejects the manifest at apply time if these don't match.

</details>

---

**Q4. What is the difference between `requests` and `limits` for CPU and memory?**

<details>
<summary>Answer</summary>

| | CPU | Memory |
|---|---|---|
| `requests` | Guaranteed allocation — scheduler uses this to place Pod on a node with enough free CPU | Guaranteed allocation — scheduler ensures node has this much free memory |
| `limits` | Hard ceiling — breach it → Pod is **throttled** (slowed, not killed) | Hard ceiling — breach it → Pod is **OOMKilled** (process killed immediately) |

Key difference: CPU overuse = throttling. Memory overuse = death.

</details>

---

**Q5. What happens under the hood during a rolling update? How does zero downtime work?**

<details>
<summary>Answer</summary>

1. `kubectl set image` tells the Deployment the desired state has changed
2. Deployment controller creates a **new ReplicaSet** for the new image version
3. New ReplicaSet scales up 1 Pod → waits for it to be Ready
4. Old ReplicaSet scales down 1 Pod
5. Repeats until new RS is at full desired count and old RS is at 0

Zero downtime works because K8s never terminates an old Pod until a new Pod is Ready. At no point are all replicas unavailable simultaneously.

</details>

---

**Q6. How does rollback work internally? Is the old version rebuilt?**

<details>
<summary>Answer</summary>

No rebuild. K8s keeps old ReplicaSets scaled to 0 but does not delete them.  
`kubectl rollout undo` simply:
- Scales the previous ReplicaSet back up to desired count
- Scales the current ReplicaSet down to 0

It's a pointer swap between existing ReplicaSets. Near-instant because the old Pods just need to be scheduled, not re-pulled (image likely cached on node).

</details>

---

**Q7. What is the reconciliation loop?**

<details>
<summary>Answer</summary>

The reconciliation loop is the core operating principle of Kubernetes.  
Every controller (ReplicaSet, Deployment, etc.) continuously watches:

```
desired state (what you declared) vs actual state (what exists in the cluster)
```

If they differ → controller takes action to close the gap.  
It never stops watching. This is why Kubernetes is **self-healing** — it's not reacting to events, it's constantly comparing and correcting.

</details>

---

**Q8. Why is mixing `kubectl set image` with `kubectl apply -f` a problem?**

<details>
<summary>Answer</summary>

`kubectl apply` uses the `last-applied-configuration` annotation stored on the resource to calculate diffs.  
`kubectl set image` updates the live resource imperatively but does NOT update that annotation.

So the next `kubectl apply` from your YAML file will overwrite the image back to what's in the file — silently undoing your `set image` change.

Production rule: pick one approach and stick to it. Declarative (`kubectl apply`) is correct for production.

</details>