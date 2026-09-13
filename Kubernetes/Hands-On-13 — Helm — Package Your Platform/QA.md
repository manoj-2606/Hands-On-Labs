# Hands-On 13 — Mastery Check

Answer these without reference. Answers are below each question.

---

**Q1. What three files/folders are required in a Helm chart?**

Every Helm chart must have:

1. **`Chart.yaml`** — chart metadata (name, version, description). Helm reads this first to identify the folder as a chart.
2. **`values.yaml`** — default configuration values. Templates reference these via `{{ .Values.xxx }}`.
3. **`templates/`** — directory containing Kubernetes manifest files with Go template syntax.

Without `Chart.yaml`, Helm won't recognize the folder as a chart. Without `values.yaml`, any `{{ .Values.xxx }}` reference in templates resolves to nil and breaks rendering. Without `templates/`, there's nothing to deploy.

---

**Q2. Why must the metadata file be named `Chart.yaml` and not `Chart.yml` or `chart.yaml`?**

Helm hardcodes exactly two filenames: `Chart.yaml` and `values.yaml`. Both are **case-sensitive** and **extension-sensitive**.

- `chart.yaml` — rejected (lowercase `c`)
- `Chart.yml` — rejected (wrong extension)
- `CHART.YAML` — rejected (wrong case)

This is a Helm spec decision, not a YAML limitation. `.yml` and `.yaml` are identical as YAML formats — Kubernetes accepts both. But Helm's source code looks for exactly `Chart.yaml` and `values.yaml`. Template files inside `templates/` can use either extension — Helm reads all YAML files in that folder regardless.

---

**Q3. What is `{{ .Values.replicaCount }}` and where does it pull its value from?**

`{{ .Values.replicaCount }}` is Go template syntax that injects a value into the rendered YAML at deploy time.

**Resolution order:**

1. If `-f values-prod.yaml` is passed and contains `replicaCount`, use that value
2. Otherwise, fall back to `values.yaml` in the chart root
3. If neither defines it, renders as nil (empty) — which will break the Kubernetes manifest

Values can also be overridden inline via `--set replicaCount=5` on the command line. Priority: `--set` > `-f override` > `values.yaml`.

The dot (`.`) in `{{ .Values }}` refers to the root scope of the template context. `.Values` specifically accesses the merged values object.

---

**Q4. What is `{{ .Release.Name }}` and where does it come from?**

`{{ .Release.Name }}` is a built-in Helm object — it comes from the **command itself**, not from any file.

```bash
helm install myrelease ./myapp
#               ↑
#        this becomes .Release.Name
```

It makes resource names unique per release:
- `helm install dev ./myapp` → `dev-app`, `dev-svc`
- `helm install prod ./myapp` → `prod-app`, `prod-svc`

Other built-in release objects:
- `{{ .Release.Namespace }}` — namespace where Helm stores release metadata
- `{{ .Release.Revision }}` — current revision number
- `{{ .Release.IsUpgrade }}` — boolean, true during `helm upgrade`
- `{{ .Release.IsInstall }}` — boolean, true during `helm install`

---

**Q5. What does `helm template` do vs `helm install`?**

| Command | What It Does |
|---|---|
| `helm template` | Renders templates locally, prints YAML to screen. Nothing touches the cluster. |
| `helm install` | Renders templates AND deploys to the cluster. Creates resources, tracks revision. |

Analogy:
- `helm template` = `terraform plan` (preview)
- `helm install` = `terraform apply` (execute)

Use `helm template` to:
- Debug template syntax before deploying
- Pipe rendered YAML to other tools (`helm template ... | kubectl diff -f -`)
- Review what will be deployed in a PR/code review

`helm template` doesn't validate against the cluster — it won't catch issues like "this namespace doesn't exist" or "this image can't be pulled."

---

**Q6. What does the `-f` flag do and can the override file be outside the chart folder?**

`-f` (or `--values`) specifies an override file that merges with the chart's `values.yaml`. Only keys specified in the override file are changed — everything else falls back to defaults.

```bash
helm install prod ./myapp -f /any/path/values-prod.yaml
```

The file can be **anywhere on disk** — it's not tied to the chart folder. The `-f` flag takes any valid file path.

**Multiple `-f` flags stack** — later files override earlier ones:

```bash
helm install prod ./myapp -f base.yaml -f prod.yaml -f prod-secrets.yaml
```

Priority: last `-f` wins for overlapping keys. `--set` overrides everything.

---

**Q7. What happens to revision numbers during upgrade and rollback?**

Every mutation creates a new revision. Revisions only increment — they never go backward.

```
helm install   → Revision 1 (Install complete)
helm upgrade   → Revision 2 (Upgrade complete)
helm rollback  → Revision 3 (Rollback to 1)
helm upgrade   → Revision 4 (Upgrade complete)
```

Each revision stores the complete values and chart version used. `helm history <release>` shows the full timeline with timestamps, status, and description.

---

**Q8. Why does rollback create revision 3 instead of reverting to revision 1?**

Rollback is a **forward operation**, not a rewind. It creates a **new revision** with the old revision's configuration. This preserves the full audit trail.

If rollback reverted to revision 1:
- You'd lose the record that revision 2 ever existed
- You wouldn't know a rollback happened
- There'd be no way to "undo the rollback" (roll forward to revision 2 again)

By creating revision 3 with description "Rollback to 1", the history shows exactly what happened and when. You can even rollback a rollback — `helm rollback myrelease 2` would create revision 4 with the revision 2 config.

This is the same principle as Git's `revert` — it creates a new commit that undoes a previous commit, rather than deleting history.

---

**Q9. What does `helm uninstall` NOT delete?**

**Namespaces.** Helm is cautious about namespace deletion because other resources (from other charts, manual deployments, or system components) might live in the same namespace.

`helm uninstall myrelease` deletes:
- All Deployments, Services, ConfigMaps, Secrets, etc. that the chart created
- The release metadata (revision history)

It does NOT delete:
- The namespace (even if the chart created it)
- PersistentVolumeClaims (by default — they have independent lifecycle)
- CRDs (Custom Resource Definitions — by Helm convention, CRDs are not deleted to prevent data loss)

You must manually run `kubectl delete namespace <name>` if you want the namespace gone.

---

**Q10. How does `helm history` help in production incident response?**

`helm history <release>` shows every revision with:
- **Timestamp** — when each change happened
- **Status** — `deployed`, `superseded`, `failed`
- **Description** — `Install complete`, `Upgrade complete`, `Rollback to 2`
- **Chart version** — which chart version was used

**Incident response workflow:**

1. App is broken after a deployment
2. `helm history myapp` → see revision 5 was deployed 10 minutes ago
3. `helm get values myapp --revision 4` → see what the previous working config was
4. `helm get values myapp --revision 5` → compare with current broken config
5. Identify the diff — maybe `replicaCount` dropped to 0 or `image.tag` is wrong
6. `helm rollback myapp 4` → instant revert, new revision 6 created
7. App restored, then investigate root cause

Without Helm, you'd be digging through Git commits, CI pipeline logs, and hoping someone remembers what changed.

---

**Q11. What is the difference between `helm install` and `helm upgrade --install`?**

- **`helm install`** — creates a new release. Fails if a release with that name already exists.
- **`helm upgrade --install`** — upgrades if the release exists, installs if it doesn't. Idempotent.

```bash
# First run: installs (creates revision 1)
helm upgrade --install myrelease ./myapp

# Second run: upgrades (creates revision 2)
helm upgrade --install myrelease ./myapp -f values-prod.yaml
```

`helm upgrade --install` is the standard in CI/CD pipelines because it works regardless of whether the release exists. You don't need separate "first deploy" and "update" logic.

---

**Q12. Where does Helm store release metadata?**

Helm stores release metadata (revision history, values, manifests) as **Secrets** in the namespace where the release was installed.

```bash
kubectl get secrets -n default -l owner=helm
```

You'll see secrets named `sh.helm.release.v1.myrelease.v1`, `sh.helm.release.v1.myrelease.v2`, etc. — one per revision. The data is base64-encoded and gzipped.

This is why `helm list -A` works without a separate database — Helm queries Kubernetes Secrets directly. It also means:
- Release metadata is backed up with your cluster
- RBAC controls who can see release data
- If you delete the namespace, you lose the release history

In Helm v2 (deprecated), metadata was stored in a server-side component called Tiller. Helm v3+ is fully client-side — no server component needed.