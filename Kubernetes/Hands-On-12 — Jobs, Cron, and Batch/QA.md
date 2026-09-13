# Hands-On 12 — Mastery Check

Answer these without reference. Answers are below each question.

---

**Q1. What is the difference between a Job and a Deployment in terms of restart behavior?**

A Deployment is designed to run **forever**. If a pod dies or exits, the Deployment controller restarts it immediately — `restartPolicy: Always` is the default and only valid option. The desired state is "N pods running at all times."

A Job is designed to **run, finish, and exit**. When a pod exits with code 0, the Job controller marks it as a successful completion — it does not restart the pod. The desired state is "N successful completions," not "N pods running."

If you used a Deployment for a database migration, it would run the migration, exit successfully, and then Kubernetes would restart it — running the migration again in an infinite loop. Jobs exist precisely for this use case.

---

**Q2. Why is `restartPolicy: Always` not allowed for Jobs?**

`restartPolicy: Always` means "restart the container every time it exits, regardless of exit code." This directly contradicts the purpose of a Job — a Job needs to detect that a container exited with code 0 and mark it as complete.

If `Always` were allowed, a successful Job container would restart forever, and the Job controller would never see a completed pod. Kubernetes enforces this at the API level — submitting a Job with `restartPolicy: Always` returns a validation error.

Only two values are valid for Jobs:
- **`Never`** — pod exits and stays in Completed/Error state. A new pod is created for retries.
- **`OnFailure`** — container restarts in-place on non-zero exit. Pod is reused, restart count increments.

---

**Q3. What does `backoffLimit: 3` mean and how many total pods does it create?**

`backoffLimit: 3` means Kubernetes will **retry 3 times** after the initial attempt fails. Total pods created = **4** (1 original + 3 retries).

After exhausting all retries, the Job status transitions through `FailureTarget` → `Failed`, and the event `BackoffLimitExceeded` is recorded. No more pods are created.

Without `backoffLimit`, the default is 6 retries. Without setting it explicitly on production Jobs, a broken task would spawn 7 pods before giving up — potentially consuming significant cluster resources if `parallelism` is high.

---

**Q4. What is exponential backoff and why does Kubernetes use it for Job retries?**

Exponential backoff means each retry waits longer than the previous one. The delay roughly doubles: ~10s, ~20s, ~40s, ~80s, and so on (capped at 6 minutes).

Kubernetes uses this because immediate retries are dangerous:
- If the failure is a transient issue (network blip, temporary resource exhaustion), a brief wait gives the system time to recover
- If the failure is persistent (bad config, expired credentials), rapid retries would flood the cluster with failing pods, waste CPU/memory, and fill up event logs
- Exponential growth means the first retry is fast (in case it was a blip) but subsequent retries give progressively more time for systemic issues to resolve

You can observe the backoff directly in `kubectl describe job` — the Events section shows pod creation timestamps with increasing gaps.

---

**Q5. What is the difference between `restartPolicy: Never` and `OnFailure` for Jobs?**

| | `Never` | `OnFailure` |
|---|---|---|
| On failure | New pod created | Same pod restarts in-place |
| Failed pods visible | Yes — all remain in `Error` state | No — only current pod visible |
| Previous logs | Readable from each individual pod | Lost on restart (overwritten) |
| Resource usage | Higher — multiple pods exist | Lower — single pod reused |
| Debugging | Easier — full history preserved | Harder — only latest attempt visible |
| `RESTARTS` column | 0 on all pods | Increments on the single pod |

**Use `Never`** when you need post-mortem debugging — you can read logs from every failed attempt. This is what you'd want for a failing migration or ETL job where each failure might have a different root cause.

**Use `OnFailure`** when the failure is expected to be transient and you don't need historical logs — saves resources by not accumulating pods.

---

**Q6. What do `completions` and `parallelism` control?**

- **`completions`** — the total number of times the task must succeed (exit 0) before the Job is marked `Complete`. Default: 1.
- **`parallelism`** — the maximum number of pods running simultaneously. Default: 1.

Example: `completions: 500`, `parallelism: 10` — process 500 items with 10 workers at a time. Kubernetes launches 10 pods. As each finishes, a new one starts. The `COMPLETIONS` counter increments: `0/500 → 1/500 → ... → 500/500`.

Kubernetes never runs more than `parallelism` pods at once. Each pod runs independently with no shared state — they don't coordinate. If you need coordination (e.g., each pod processes a specific partition), use `completionMode: Indexed` which gives each pod a unique `JOB_COMPLETION_INDEX` environment variable.

---

**Q7. What is a CronJob and what three-layer chain does it create?**

A CronJob is a scheduled Job — it creates new Jobs at specified intervals using standard cron syntax (`"*/5 * * * *"` = every 5 minutes).

The three-layer chain:

```
CronJob → Job → Pod
```

- **CronJob** watches the clock and creates a new **Job** object on each schedule trigger
- The **Job** controller creates a **Pod** to execute the work
- The **Pod** runs the container, exits, and the Job tracks completion

This means CronJob-created Jobs have auto-generated names (e.g., `scheduled-job-29821425`) with a timestamp suffix. You can't predict the Job name in advance — you query by labels or by listing Jobs under the CronJob.

A CronJob is to a Job what a Deployment is to a Pod — a higher-level controller that manages the lifecycle of the resource below it.

---

**Q8. What does `concurrencyPolicy: Forbid` do?**

If a scheduled trigger fires while the previous Job is still running, `Forbid` **skips the new run entirely**. No new Job is created. The in-progress Job continues undisturbed.

Three options:

| Policy | Behavior |
|---|---|
| `Allow` | New Job created even if previous is still running. Jobs overlap. |
| `Forbid` | New Job skipped if previous is active. No overlap. |
| `Replace` | Previous Job is terminated. New Job starts. |

**Use `Forbid`** for operations that must not overlap — database backups, report generation, anything that would corrupt data or produce duplicates if two instances ran simultaneously.

**Use `Replace`** when the latest run's data supersedes the previous — e.g., a cache rebuild where only the freshest result matters.

**Use `Allow`** only when runs are fully independent and overlap is safe.

---

**Q9. What does `successfulJobsHistoryLimit` prevent?**

It prevents **Job and Pod pile-up**. Without it, every scheduled run leaves behind a completed Job object and its associated Pod in the cluster. Over days and weeks, this accumulates thousands of objects — consuming etcd storage, slowing down `kubectl get jobs`, and bloating the API server.

`successfulJobsHistoryLimit: 3` keeps only the last 3 completed Jobs. When the 4th succeeds, the oldest is automatically deleted along with its Pod.

`failedJobsHistoryLimit: 2` does the same for failed Jobs — keeps the last 2 for debugging, auto-deletes older ones.

In production, these should always be set explicitly. The default `successfulJobsHistoryLimit` is 3 and `failedJobsHistoryLimit` is 1, but making it explicit in YAML prevents surprises.

---

**Q10. What are the two-phase status transitions for Job completion and failure?**

Jobs don't jump directly to their final status. They transition through an intermediate state:

**Success path:**
```
Running → SuccessCriteriaMet → Complete
```

**Failure path:**
```
Running → FailureTarget → Failed
```

The intermediate state (`SuccessCriteriaMet` / `FailureTarget`) is Kubernetes marking **intent** before finalizing. This two-phase transition allows controllers and webhooks to observe the pending state change and react before it's committed.

You can observe both transitions in real-time using `kubectl get jobs -w`. The intermediate state appears briefly before the final status is set.

---

**Q11. What is `ttlSecondsAfterFinished` and when would you use it?**

`ttlSecondsAfterFinished` is a Job-level field that auto-deletes the Job (and its Pods) after a specified number of seconds post-completion or failure.

```yaml
spec:
  ttlSecondsAfterFinished: 3600  # Delete 1 hour after finishing
```

This is an alternative to `successfulJobsHistoryLimit` on CronJobs. Use it for standalone Jobs (not CronJob-managed) where you want automatic cleanup without manual `kubectl delete`.

Setting it to `0` deletes the Job immediately after completion — useful for fire-and-forget tasks where you don't need logs. But be careful: once deleted, logs are gone permanently.

---

**Q12. What happens when a CronJob misses more than 100 scheduled runs?**

If the CronJob controller (part of kube-controller-manager) is down or unable to create Jobs for long enough that **more than 100 consecutive schedules are missed**, the CronJob stops scheduling entirely and logs an error:

```
Cannot determine if job needs to be started. Too many missed start time (> 100).
```

This is a safety mechanism — if the controller was down for days, you probably don't want it to suddenly fire 500 backlogged Jobs at once.

`startingDeadlineSeconds` controls the window for counting missed schedules. Setting it to a value (e.g., `200`) means Kubernetes only counts missed schedules within the last 200 seconds. If the controller recovers within that window, it creates the Job for the most recent missed schedule and continues normally.