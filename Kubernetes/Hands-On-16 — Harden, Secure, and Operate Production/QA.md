# Hands-On 16 — Mastery Check

Answer these without reference. Answers are below each question.

---

**Q1. What is Kyverno and how does it work?**

Kyverno is a Kubernetes-native policy engine that runs as an **admission webhook**. When you `kubectl apply` any resource, the Kubernetes API server sends the request to Kyverno before writing it to etcd. Kyverno evaluates the resource against all active ClusterPolicies. If the resource violates a policy with `validationFailureAction: Enforce`, Kyverno returns a rejection and the API server rejects the request. The pod is never scheduled — it never reaches a node.

Kyverno is installed as a Deployment inside the cluster. It registers itself as a ValidatingAdmissionWebhook with the API server. Every resource creation or update goes through it automatically.

Key fields in a ClusterPolicy:
- `validationFailureAction: Enforce` — hard block. `Audit` only logs.
- `background: true` — also evaluates existing resources, not just new ones
- `match` — which resource kinds this rule applies to
- `exclude` — namespaces or resources to skip (system namespaces must be excluded)
- `validate.pattern` — the shape the resource must match

---

**Q2. What are the three Kyverno policies in this lab and what does each enforce?**

**`disallow-root-containers`** — requires every container to have `runAsNonRoot: true` and `runAsUser >= 1000`. Excludes `kube-system`, `kyverno`, `trivy-system` because those namespaces run system workloads that need root. Our app runs as UID 1001 — satisfies this.

**`require-resource-limits`** — requires every container to declare `resources.limits.cpu` and `resources.limits.memory`. Without limits, a single pod can consume all node CPU/memory and kill other pods. Our app declares `cpu: 200m` and `memory: 128Mi`.

**`acr-images-only`** — requires all images to come from `acrgitopslab16.azurecr.io/*`. Blocks supply chain attacks via public Docker Hub images. Excludes system namespaces that pull from public registries legitimately. Our app image is pushed to ACR — satisfies this.

---

**Q3. What are Pod Security Standards and how are they different from Kyverno?**

Pod Security Standards (PSS) are a Kubernetes-native security baseline applied via **namespace labels**. No extra tool needed — built into Kubernetes itself.

Three profiles:
- `privileged` — no restrictions
- `baseline` — blocks known privilege escalation techniques
- `restricted` — production-grade hardening. Blocks privileged containers, root user, host network/PID/IPC access. Requires dropping ALL capabilities and `allowPrivilegeEscalation: false`.

Applied via labels:
```yaml
pod-security.kubernetes.io/enforce: restricted  # reject violating pods
pod-security.kubernetes.io/audit: restricted    # log violations
pod-security.kubernetes.io/warn: restricted     # warn on kubectl
```

**PSS vs Kyverno:**

| | Pod Security Standards | Kyverno |
|---|---|---|
| Built into K8s | Yes — zero install | No — deployed as webhook |
| Scope | Pod security fields only | Any K8s resource, any field |
| Custom rules | No — fixed profiles | Yes — write any rule |
| Registry enforcement | No | Yes |
| Resource limits | No | Yes |
| Mutation | No | Yes — auto-inject defaults |

PSS is the fast baseline. Kyverno covers everything PSS can't. Use both.

---

**Q4. What is `validationFailureAction: Enforce` vs `Audit`?**

`Enforce` — **hard block**. The API server rejects the request. Pod never created. The user sees:
```
Error from server (Forbidden): admission webhook denied the request
```

`Audit` — **soft log**. The resource is allowed through. Kyverno logs the violation as a PolicyReport CRD. No rejection. Used during migration to discover violations without breaking anything.

Production always uses `Enforce`. Start with `Audit` during migration, then switch to `Enforce` after all violations are fixed.

---

**Q5. What is the Trivy Operator and how is it different from pipeline Trivy?**

Both use Trivy to scan for CVEs. They operate at completely different points:

| | Pipeline Trivy (Stage 2) | Trivy Operator |
|---|---|---|
| When | Before image is pushed | After pod is deployed |
| What | Image tar on MS-hosted VM | Live pod image in AKS |
| Output | Pipeline pass/fail | VulnerabilityReport CRD |
| Frequency | Once at build time | Continuously — rescans periodically |
| Blocks | Yes — `--exit-code 1` | No — reports only |

**Why both are needed:** Pipeline Trivy catches CVEs before they enter the cluster. Trivy Operator catches CVEs discovered after deployment — the CVE database updates daily. An image clean at build time can have a new critical CVE a week later. Trivy Operator tracks this continuously and creates `VulnerabilityReport` CRDs you can query with `kubectl get vulnerabilityreport`.

---

**Q6. Why did Trivy Operator fail in this lab and how was it fixed?**

**What happened:** Trivy Operator creates scan Jobs in `trivy-system` to scan pods. Those Jobs run as root internally. Kyverno's `disallow-root-containers` policy had no `exclude` for `trivy-system`. So Kyverno blocked every scan Job Trivy tried to create. Trivy could never scan anything — no VulnerabilityReports were generated.

**The error in logs:**
```
creating scan job failed: trivy-system/scan-vulnerabilityreport-xxx
admission webhook denied: disallow-root-containers
autogen-check-runAsNonRoot failed
```

**The fix:** Add `trivy-system` to the `exclude` block in `policy-no-root.yml`:
```yaml
exclude:
  any:
  - resources:
      namespaces:
      - kube-system
      - kyverno
      - trivy-system    # ← added this
```

This lets Trivy's internal scan Jobs run as root in `trivy-system` while still enforcing the non-root rule on all application namespaces.

---

**Q7. What is Azure Key Vault and why is it used instead of Kubernetes Secrets?**

**Kubernetes Secrets problem:** Secrets are stored in etcd as base64. Base64 is not encryption — anyone with cluster access can decode them:
```bash
kubectl get secret db-creds -o jsonpath='{.data.password}' | base64 -d
# → mypassword (plain text)
```

**Azure Key Vault:** Secrets are encrypted at rest using Azure-managed keys. Access is controlled via Azure RBAC. Every read is logged in Azure Monitor. Rotation is automatic. The secret never touches Kubernetes.

**In this lab:**
- Secret `db-password` lives only in Key Vault
- Never in Git, never in a K8s manifest, never in etcd
- CSI driver fetches it at pod start and mounts it as a TMPFS file
- `kubectl get secret -n secured-app` returns nothing

---

**Q8. What is the Secrets Store CSI Driver and what is TMPFS?**

**CSI Driver** — bridges Azure Key Vault and Kubernetes. At pod start, the CSI driver reads the `SecretProviderClass` CRD, authenticates to Key Vault via Workload Identity, fetches the secret value, and mounts it as a file inside the pod.

**TMPFS** — temporary filesystem that lives only in RAM. The mounted file at `/mnt/secrets/db-password` is:
- Not written to the node disk
- Not stored in etcd
- Not visible to other pods
- Gone when the pod stops

**The chain:**
```
Key Vault → CSI driver (authenticated via MI) → TMPFS mount → /mnt/secrets/db-password
```

---

**Q9. What is Workload Identity and how does it work in this lab?**

Workload Identity allows a Kubernetes ServiceAccount to authenticate to Azure services without any stored credentials.

**The chain:**
1. AKS cluster has OIDC issuer enabled (`--enable-oidc-issuer`)
2. Azure Managed Identity `mi-secured-app` is created
3. A Federated Credential links the MI to the K8s ServiceAccount:
   - Issuer: AKS OIDC URL
   - Subject: `system:serviceaccount:secured-app:secured-app-sa`
4. The ServiceAccount is annotated with the MI client ID
5. The pod uses `serviceAccountName: secured-app-sa`
6. When the CSI driver needs to call Key Vault, it uses the pod's ServiceAccount token to get an Azure access token for the MI
7. The MI has `Key Vault Secrets User` RBAC role on the vault
8. Key Vault returns the secret

No password. No secret. No rotation. The federation is the credential.

---

**Q10. What does Test 1 in VerifySecurity prove and why is the assertion inverted?**

Test 1 proves Kyverno and PSS are actually enforcing — not just installed.

It deliberately applies `test-privileged-pod.yml` which violates all rules:
- `privileged: true` — blocked by PSS restricted
- `runAsUser: 0` — blocked by Kyverno disallow-root-containers
- `image: nginx` — blocked by Kyverno acr-images-only
- No resource limits — blocked by Kyverno require-limits

**The assertion is inverted:**
```bash
if kubectl apply -f test-privileged-pod.yml 2>&1; then
  exit 1  # apply succeeded = security broken = pipeline fails
else
  echo "✅ PASSED"  # apply failed = security working = pipeline passes
fi
```

A normal test passes when the command succeeds. This test passes when the command **fails**. It's testing that the cluster correctly rejects something it should reject.

**Why this matters:** Kyverno could be installed but misconfigured — wrong webhook selector, policy in Audit mode. The cluster would look secure but allow anything. This test catches that by actually trying to break the rules.

---

**Q11. What does Test 2 in VerifySecurity prove?**

Test 2 proves Trivy Operator is running and successfully scanning the deployed pod.

It polls every 10 seconds for up to 3 minutes:
```bash
REPORT_COUNT=$(kubectl get vulnerabilityreport -n secured-app --no-headers | wc -l)
```

A `VulnerabilityReport` CRD appearing in `secured-app` proves:
- Trivy Operator is running in `trivy-system`
- Its scan Jobs are not being blocked by Kyverno (trivy-system is excluded)
- Trivy can authenticate to ACR to pull and scan the image
- The operator successfully scanned `secured-app-pod` and wrote results

If no report appears after 3 minutes, it means Trivy Operator's scan Jobs are failing — most likely due to Kyverno blocking them or ACR auth issues.

---

**Q12. What does Test 3 in VerifySecurity prove and why is the secret value redacted?**

Test 3 proves the full Key Vault → CSI → TMPFS → pod chain is working end to end.

```bash
SECRET_VALUE=$(kubectl exec secured-app-pod -n secured-app -- cat /mnt/secrets/db-password)
```

If the file is readable and non-empty, it proves:
- Key Vault has the secret
- The MI has correct RBAC permissions
- The federated credential is correctly configured
- The SecretProviderClass points to the right vault and secret
- The CSI driver successfully fetched and mounted the secret
- The pod's security context allows reading the mount

**Why the value is redacted:** The pipeline logs `Secret length: N characters` instead of the actual value. ADO pipeline logs are visible to anyone with project access. Printing the actual secret value would defeat the purpose of using Key Vault — the secret would be exposed in plain text in the pipeline logs.

---

**Q13. What is the SecretProviderClass and what does each field do?**

```yaml
apiVersion: secrets-store.csi.x-k8s.io/v1
kind: SecretProviderClass
metadata:
  name: azure-keyvault-secrets
  namespace: secured-app
spec:
  provider: azure
  parameters:
    usePodIdentity: "false"
    clientID: "<MI-client-id>"      # which Managed Identity to auth as
    keyvaultName: "kv-gitops-lab16" # which Key Vault to connect to
    tenantID: "<tenant-id>"          # Azure tenant
    objects: |
      array:
        - |
          objectName: db-password   # name of the secret in Key Vault
          objectType: secret
          objectVersion: ""         # "" = always latest version
```

- `provider: azure` — use the Azure Key Vault provider
- `clientID` — which MI to authenticate as (patched by `sed` in pipeline)
- `keyvaultName` — which vault to connect to
- `objects` — list of secrets to fetch. Each becomes a file in the TMPFS mount.

The SecretProviderClass is referenced in the pod's volume definition. At pod start, the CSI driver reads this CRD and fetches all listed objects.

---

**Q14. What is the `bad-pod` and why does it violate all four security controls?**

```yaml
spec:
  containers:
  - name: bad-container
    image: nginx              # public Docker Hub → violates acr-images-only
    securityContext:
      privileged: true        # full node access → violates PSS restricted
      runAsUser: 0            # root (UID 0) → violates disallow-root-containers
    # no resources block      # → violates require-resource-limits
```

Four violations simultaneously:

| Violation | Blocked By |
|---|---|
| `image: nginx` (public registry) | Kyverno `acr-images-only` |
| `runAsUser: 0` (root) | Kyverno `disallow-root-containers` |
| `privileged: true` | Pod Security Standards `restricted` |
| No resource limits | Kyverno `require-resource-limits` |

The pod is used as the Test 1 weapon — the pipeline applies it and asserts it gets rejected. One pod, four violations, one rejection. Clean proof that all admission controls are active.

---

**Q15. What is the end-to-end flow of this lab from pipeline trigger to proof?**

```
Pipeline triggers
       ↓
Provision: RG + ACR + AKS + Key Vault + Workload Identity + CSI addon
       ↓
[Parallel]
Track 1: Build (USER 1001) → Scan (Trivy) → Push (ACR via MI)
Track 2: SetupSecurity → Install Kyverno → Install Trivy Operator
                       → Apply 3 ClusterPolicies
                       → Label secured-app namespace with PSS restricted
       ↓
Deploy (env gate — approval):
  Patch SecretProviderClass with MI client ID + tenant ID
  Patch pod-with-secret.yml with ACR image
  kubectl apply SecretProviderClass
  kubectl apply pod-with-secret.yml
  Wait for pod Ready (CSI driver must mount KV secret)
       ↓
VerifySecurity:
  Test 1: kubectl apply bad-pod → MUST be rejected by Kyverno + PSS ✅
  Test 2: Poll for VulnerabilityReport → Trivy Operator scanned pod ✅
  Test 3: kubectl exec cat /mnt/secrets/db-password → non-empty ✅
       ↓
ALL SECURITY TESTS PASSED
Four layers proven. Platform is hardened.
```