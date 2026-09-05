# Hands-On 5 — Mastery Check

Answer these without reference. Answers are below each question.

---

**Q1. What is the difference between Liveness and Readiness probes?**

Liveness answers: "Is the app still functional?" Failure → container killed and restarted.
Readiness answers: "Is the app ready to receive traffic?" Failure → pod removed from Service endpoints, container NOT restarted.

Key difference: Liveness restarts. Readiness just pulls from traffic. A pod can be Running + not Ready (0/1) — container alive but not serving requests.

---

**Q2. What is the purpose of the Startup probe? When must you use it?**

Startup probe blocks liveness and readiness from firing until the app finishes starting. Once it passes, it never runs again.

Use it when: app takes longer to boot than `initialDelaySeconds` + (`failureThreshold` × `periodSeconds`) of the liveness probe allows. Without it, liveness kills the container before it finishes booting — infinite restart loop.

Max startup window = `failureThreshold` × `periodSeconds`. Example: 10 × 5 = 50 seconds.

---

**Q3. What happens step by step when a Liveness probe fails 3 consecutive times?**

1. Probe runs → exit code non-zero or timeout → failure count +1
2. Repeats until `failureThreshold` (3) consecutive failures
3. kubelet kills the container
4. kubelet restarts the container (respecting restart policy)
5. Failure count resets
6. `initialDelaySeconds` does NOT apply on restart — probe starts immediately

---

**Q4. Why did the Liveness probe keep restarting even after you created `/tmp/healthy` manually?**

Every container restart wipes the filesystem. The file you created manually was gone on each restart — fresh container, file missing, probe fails again, restart again. Infinite loop.

Fix: the app itself must create the health signal on startup:
```yaml
command: ["sh", "-c", "touch /tmp/healthy && sleep 3600"]
```

Health signals must survive as part of the startup sequence, not be injected manually.

---

**Q5. What is OOMKilled? What triggers it and who handles the restart?**

OOMKilled = the Linux kernel killed the container process because it exceeded its memory `limit`. No warning. Instant kill.

Triggered by: container RAM usage exceeding the `limits.memory` value in the pod spec.

Restart handled by: kubelet — not the ReplicaSet. kubelet detects the container exited and restarts it on the same node.

OOMKill is a RAM issue only. Disk writes (`/tmp`, `/dev/null`) do not count against memory limits.

---

**Q6. What is CrashLoopBackOff? Is it a problem itself or a symptom?**

Symptom, not a root cause. CrashLoopBackOff means: the container keeps crashing and kubelet is applying exponential backoff before retrying.

Backoff schedule: 10s → 20s → 40s → 80s → max 5 minutes.

Purpose: prevents a broken container from hammering the node with rapid restarts.

Root causes it indicates: OOMKilled, bad command, missing config, application crash on startup. Always `kubectl describe` and check logs to find the real cause.

---

**Q7. What is the difference between kubelet and ReplicaSet in terms of restart behavior?**

| | kubelet | ReplicaSet |
|---|---|---|
| Scope | Single node | Cluster-wide |
| Trigger | Container exits for any reason | Pod count drops below desired |
| Action | Restarts container on same node | Creates new pod, scheduler assigns node |
| OOMKill | ✅ handled by kubelet | ❌ not involved |
| Node failure | ❌ kubelet is dead | ✅ ReplicaSet reschedules on healthy node |

OOMKill → kubelet restarts. Node dies → ReplicaSet reschedules.

---

**Q8. A pod is `0/1 Running` with 0 restarts. What does this tell you?**

Readiness probe is failing. The container is alive and running — kubelet has not killed it. But the readiness check is not passing, so Kubernetes has removed the pod from the Service endpoints. It is receiving zero traffic.

This is not a liveness failure. No restart will happen unless you also have a liveness probe failing independently.

Diagnose with:
```bash
kubectl describe pod <pod-name> -n <namespace>
# Look at: Conditions section and Events section
```