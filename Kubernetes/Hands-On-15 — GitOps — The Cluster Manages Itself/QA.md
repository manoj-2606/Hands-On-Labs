# Hands-On 15 — Mastery Check

Answer these without reference. Answers are below each question.

---

**Q1. What is GitOps and what is the core principle behind it?**

GitOps is an operational model where **Git is the single source of truth** for everything that runs in your cluster. Every desired state change — deploy a new image, scale a deployment, add a ConfigMap — is expressed as a Git commit. A GitOps agent (ArgoCD) continuously compares what Git says should exist against what the cluster actually contains, and reconciles any difference.

The core principle: **the cluster must always converge to match Git. No exceptions.**

This means:
- No direct `kubectl apply` in production
- No `helm upgrade` from a pipeline talking directly to AKS
- Every deployment is a commit. Every rollback is a `git revert`.
- Git history is your complete audit trail of cluster state

---

**Q2. What is ArgoCD and where does it run?**

ArgoCD is a GitOps continuous delivery tool. It runs **inside the Kubernetes cluster** as a set of pods in the `argocd` namespace — not as an external service. It's a workload like anything else you deploy.

ArgoCD consists of several components:
- **argocd-server** — the API server and UI
- **argocd-repo-server** — clones Git repos, renders manifests
- **argocd-application-controller** — compares desired state (Git) with actual state (cluster), triggers syncs
- **argocd-dex-server** — SSO/auth
- **argocd-redis** — caching

The application-controller is the core. Every 3 minutes (default), it fetches the latest Git state and compares it to the cluster. If they differ, it applies the Git version.

In this lab: installed via `helm upgrade --install argocd argo/argo-cd` into the `argocd` namespace on AKS.

---

**Q3. What is the ArgoCD Application CRD and what does each field do?**

The Application CRD is ArgoCD's custom resource that defines the contract between a Git path and a cluster namespace.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: gitops-app
  namespace: argocd          # Must be in argocd namespace
spec:
  project: default
  source:
    repoURL: https://dev.azure.com/...    # Git repo to watch
    targetRevision: main                  # Branch to track
    path: "Kubernetes/.../k8s-manifests"  # Folder inside repo
  destination:
    server: https://kubernetes.default.svc  # Deploy to this cluster (local = default.svc)
    namespace: gitops-lab                   # Target namespace
  syncPolicy:
    automated:
      prune: true       # Delete resources removed from Git
      selfHeal: true    # Revert manual cluster changes to match Git
    syncOptions:
    - CreateNamespace=true  # Create namespace if it doesn't exist
```

- **`source`** — where to read desired state from
- **`destination`** — where to apply it
- **`automated`** — enables auto-sync without human clicking "Sync" in the UI
- **`selfHeal`** — the key flag that makes Git the enforced truth
- **`prune`** — prevents orphaned resources when manifests are removed from Git

---

**Q4. What does `selfHeal: true` actually do? Give a concrete example.**

`selfHeal: true` means ArgoCD watches the cluster for any deviation from Git state and automatically corrects it — without human intervention.

**Concrete example from this lab:**

```bash
# Someone runs this directly on the cluster:
kubectl scale deployment gitops-app --replicas=5 -n gitops-lab
# Cluster now has 5 pods. Git says 2.

# ArgoCD detects on next sync cycle (within 3 minutes):
# Desired state (Git): replicas: 2
# Actual state (cluster): replicas: 5
# Diff detected → DRIFT

# ArgoCD applies the Git version:
# kubectl apply -f deployment.yml (which has replicas: 2)
# Cluster reverts to 2 pods. Automatically.
```

This is why `selfHeal: true` is the most important production setting. It enforces the contract: **Git is the only control plane. Nobody talks to the cluster directly.**

Without `selfHeal: true`, ArgoCD would detect the drift and show it as OutOfSync, but not fix it automatically.

---

**Q5. What is `prune: true` and what happens without it?**

`prune: true` tells ArgoCD: if a resource exists in the cluster but its manifest no longer exists in Git, **delete it from the cluster**.

**Without `prune: true`:**
```
Git: deployment.yml + service.yml
ArgoCD syncs → both exist in cluster

You delete service.yml from Git and push
ArgoCD syncs → deploys deployment.yml
But Service still exists in cluster — orphaned, not managed by anyone
```

**With `prune: true`:**
```
You delete service.yml from Git and push
ArgoCD syncs → deploys deployment.yml
ArgoCD also deletes the Service from cluster
Cluster matches Git exactly
```

Production always uses `prune: true`. Without it, deleted resources accumulate in the cluster over time. This creates drift, confusing states, and potential security issues (old services still exposed).

---

**Q6. What is the Manifest Update Pattern and why doesn't the pipeline deploy directly to AKS?**

The Manifest Update Pattern is the GitOps approach to CI/CD:

**Pipeline does NOT do this (traditional):**
```
Build image → Push to ACR → kubectl apply to AKS (pipeline talks to AKS directly)
```

**Pipeline DOES this (GitOps):**
```
Build image → Push to ACR → Update image tag in deployment.yml → git push
                                      ↓
                          ArgoCD detects Git change → syncs AKS
```

The pipeline never talks to AKS in the UpdateManifest stage. It only writes to Git.

**Why?**
- Pipeline kubeconfig = credential that can do anything in the cluster. Risky.
- With GitOps, the pipeline only needs Git write access — much smaller blast radius
- Every deployment is a trackable Git commit — full audit trail
- Rollback = `git revert` + ArgoCD syncs. Clean, fast, auditable.
- If the pipeline fails after the git push, ArgoCD still syncs. If `kubectl apply` fails mid-pipeline, the cluster is in an unknown state.

In this lab: `sed -i "s|image:.*|image: ${FULL_IMAGE}|" deployment.yml` → `git commit` → `git push`. That's the entire deploy mechanism.

---

**Q7. Why is `[skip ci]` in the commit message of the UpdateManifest stage?**

The pipeline's UpdateManifest stage commits to the same `main` branch that triggers the pipeline. Without `[skip ci]`, the commit would trigger the pipeline again — which would build a new image, push it, update the manifest, push another commit — infinite loop.

`[skip ci]` is an ADO convention that tells the pipeline trigger to ignore this commit.

```bash
git commit -m "chore: update gitops-app to $(imageTag) [skip ci]"
```

ADO reads `[skip ci]` in the commit message and skips triggering a new pipeline run. This prevents the pipeline from running itself into an infinite loop.

---

**Q8. How does ArgoCD authenticate to the private ADO repo without a PAT?**

In this lab, we use Managed Identity (MI) to fetch a short-lived Azure DevOps access token at pipeline runtime:

```bash
ADO_TOKEN=$(az account get-access-token \
  --resource 499b84ac-1321-427f-aa17-267ca6975798 \
  --query accessToken -o tsv)
```

The resource GUID `499b84ac-1321-427f-aa17-267ca6975798` is Azure DevOps's fixed resource ID. The MI identity authenticated by the pipeline requests a token for this resource. The token is valid for ~1 hour.

This token is injected into a Kubernetes secret in the `argocd` namespace:

```bash
kubectl create secret generic ado-repo-creds \
  --from-literal=type=git \
  --from-literal=url="https://dev.azure.com/..." \
  --from-literal=username=bearer \
  --from-literal=password="${ADO_TOKEN}"

kubectl label secret ado-repo-creds \
  argocd.argoproj.io/secret-type=repository
```

The label `argocd.argoproj.io/secret-type=repository` is how ArgoCD auto-discovers repo credentials without manual CLI registration.

**No PAT stored anywhere. No secret rotation needed for CI. Token is disposable.**

Production note: the token is valid for 1 hour. ArgoCD caches the clone. For long-running clusters, you'd want a CronJob to rotate this secret periodically, or use ArgoCD Image Updater which handles auth differently.

---

**Q9. What is `persistCredentials: true` in the checkout step and why is it needed?**

```yaml
- checkout: self
  fetchDepth: 1
  persistCredentials: true
```

By default, ADO's checkout step fetches the repo and then removes the Git credentials from the local config — it assumes you only need to read the repo. After checkout, if you try to `git push`, you'll get an authentication error.

`persistCredentials: true` tells ADO to keep the credentials in the local Git config after checkout, so subsequent `git push` commands in the same job can authenticate.

Without it, the UpdateManifest stage would fail at `git push origin main` with a 403.

---

**Q10. What is the difference between ArgoCD and the pipeline's Deploy stage from Project04?**

| Project04 Deploy Stage | ArgoCD (Hands-On 15) |
|---|---|
| Pipeline VM authenticates to AKS with kubeconfig | ArgoCD runs inside AKS — no external kubeconfig |
| `helm upgrade --install` runs from pipeline VM | ArgoCD applies manifests from within the cluster |
| Deployment happens when pipeline runs | Deployment happens when Git changes |
| No drift detection after deploy | Continuous drift detection every 3 minutes |
| Rollback = re-run pipeline with old image | Rollback = `git revert` + ArgoCD syncs |
| Pipeline failure = unknown cluster state | ArgoCD retries until convergence |
| Pipeline has direct AKS credentials | Pipeline only has Git write access |

Project04's approach (Helm in pipeline) works. But it couples the deploy mechanism to pipeline availability, stores AKS credentials in the pipeline, and has no drift detection.

---

**Q11. What is drift in GitOps and how does ArgoCD handle it?**

**Drift** = any difference between what Git says should be in the cluster and what is actually in the cluster.

Drift happens when:
- An engineer runs `kubectl edit` or `kubectl delete` directly
- A pod crashes and the container count changes
- Someone manually scales a deployment
- A configmap is changed directly

ArgoCD handles drift in two ways depending on configuration:

**Without `selfHeal: true`:**
- ArgoCD detects drift, marks Application as `OutOfSync`
- Shows the diff in the UI
- Does nothing automatically — requires human to click "Sync"

**With `selfHeal: true` (this lab):**
- ArgoCD detects drift on next sync cycle
- Immediately applies the Git version to the cluster
- Cluster converges back to Git state
- Application returns to `Synced` state

The sync cycle is every 3 minutes by default. In production with webhooks configured, it's near-instant.

---

**Q12. What happens end-to-end when you push a code change after the pipeline is set up?**

```
1. You push a code change to main
2. ADO pipeline triggers (trigger: none in this lab — manual only; in real setup: trigger: - main)
3. Provision stage — idempotent, RG/ACR/AKS already exist, no changes
4. Build stage — new Docker image built with new code
5. Scan stage — Trivy scans new image, passes (no new CVEs)
6. Push stage — new image pushed to ACR: acrgitopslab.azurecr.io/gitops-app:<new-sha>
7. SetupArgoCD stage — ArgoCD already installed, helm upgrade --install is idempotent
8. UpdateManifest stage — approval gate pauses pipeline
9. Reviewer approves in ADO
10. sed replaces image tag in deployment.yml: image: acrgitopslab.azurecr.io/gitops-app:<new-sha>
11. git commit -m "chore: update gitops-app to <new-sha> [skip ci]"
12. git push origin main
13. ADO sees [skip ci] — no new pipeline triggered
14. ArgoCD polls Git within 3 minutes
15. Detects deployment.yml changed (image tag differs)
16. Applies updated deployment.yml to AKS
17. AKS performs rolling update — new pods with new image, old pods terminated
18. Liveness/readiness probes pass on new pods
19. ArgoCD Application: Synced + Healthy
20. Users hit the new version of the app
```

Zero `kubectl` commands. Zero manual cluster interaction after the approval.

---

**Q13. Why does AKS auto-scaling (HPA) not replace the need for ArgoCD?**

They solve completely different problems and operate at different layers.

**HPA answers:** "How many pods should be running right now based on current load?"
- Trigger: CPU/memory metrics exceeding a threshold
- Action: Add or remove pod replicas
- Scope: Runtime scaling decisions

**ArgoCD answers:** "Does what's running in the cluster match what Git says should be running?"
- Trigger: Git commit or detected drift
- Action: Apply/update/delete K8s resources
- Scope: Desired state management for all resource types

They work in parallel without conflict:

```
ArgoCD deploys deployment.yml with replicas: 2 from Git
         ↓
HPA scales to 8 pods when CPU > 70%
         ↓
Traffic drops — HPA scales back to 2
         ↓
New code pushed — pipeline updates image tag in Git
         ↓
ArgoCD syncs — rolling update with new image
         ↓
HPA continues managing count on top of new image
```

ArgoCD owns **what runs and how it's configured**. HPA owns **how many instances run at runtime**. Neither replaces the other.

---

**Q14. Why does the pipeline need Build Service Contribute permission and why didn't previous labs need it?**

All previous labs (Project01–Project04, Hands-On 1–14) never wrote back to the Git repo from inside the pipeline. They were consumers of the repo — read-only.

The UpdateManifest stage does:
```bash
git add deployment.yml
git commit -m "chore: update image tag [skip ci]"
git push origin main
```

This is a **write operation to the repo** from the pipeline VM. The pipeline runs as the ADO Build Service account — a separate identity from you. That account has no push rights by default.

**Permission path:**
Project Settings → Repos → Security → `Hands-On-Labs Build Service` → Contribute = Allow

Without this, `git push` returns HTTP 403 and the stage fails even though every previous stage passed.

---

**Q15. What is the complete end-to-end flow from code push to live app, with every component named?**

```
Developer: git push origin main
                │
                ▼
ADO Pipelines: pipeline triggers
                │
    ┌───────────┴──────────────┐
    ▼                          ▼
Stage: Provision           Stage: SetupArgoCD
az group create            az aks get-credentials
az acr create              helm install argo/argo-cd
az aks create              MI token → kubectl create secret ado-repo-creds
az aks get-credentials     kubectl label secret argocd.argoproj.io/secret-type=repository
                           kubectl apply application.yml
    │                          │
    ▼                          │
Stage: Build                   │
docker build --target runtime  │
docker save → image.tar.gz     │
PublishPipelineArtifact        │
    │                          │
    ▼                          │
Stage: Scan                    │
trivy image --exit-code 1      │
(blocks on CRITICAL/HIGH)      │
PublishPipelineArtifact        │
    │                          │
    ▼                          │
Stage: Push                    │
az acr login (MI)              │
docker push :commit-sha        │
docker push :latest            │
    │                          │
    └──────────┬───────────────┘
               ▼
    Stage: UpdateManifest
    [environment gate — approval]
    sed: IMAGE_PLACEHOLDER → acr.io/gitops-app:sha
    git commit [skip ci]
    git push origin main
               │
               ▼
    ADO Git repo: deployment.yml updated
               │
               ▼
    ArgoCD (inside AKS): polls Git every 3 min
    Detects: deployment.yml image tag changed
    Compares: Git state vs cluster state → OutOfSync
               │
               ▼
    ArgoCD applies:
    kubectl apply namespace.yml → gitops-lab namespace
    kubectl apply deployment.yml → 2 pods rolling update
    kubectl apply service.yml → LoadBalancer IP
               │
               ▼
    AKS: new pods pass liveness + readiness probes
    ArgoCD: Application → Synced + Healthy
               │
               ▼
    User: curl http://<external-ip>
    Response: {"message": "Hands-On 15 — GitOps is live"}
```

---

**Q16. How do you prove GitOps self-healing is working after the lab completes?**

```bash
# Step 1: Check current state
kubectl get deployment gitops-app -n gitops-lab
# Output: 2/2 ready

# Step 2: Manually bypass Git and scale to 5
kubectl scale deployment gitops-app --replicas=5 -n gitops-lab

# Step 3: Verify cluster now has 5 pods
kubectl get pods -n gitops-lab
# Output: 5 pods running

# Step 4: Check ArgoCD sees the drift
# ArgoCD UI → gitops-app → Status: OutOfSync
# Or:
kubectl get application gitops-app -n argocd -o jsonpath='{.status.sync.status}'
# Output: OutOfSync

# Step 5: Wait up to 3 minutes (ArgoCD sync interval)
# ArgoCD detects: Git says replicas: 2, cluster has replicas: 5 — DRIFT
# selfHeal: true → ArgoCD applies deployment.yml from Git

# Step 6: Verify revert
kubectl get pods -n gitops-lab
# Output: 2 pods running — back to Git state

kubectl get application gitops-app -n argocd -o jsonpath='{.status.sync.status}'
# Output: Synced
```

Git wins. Every time. That's the proof.