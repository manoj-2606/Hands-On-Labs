# Hands-On 4 — Config Without Chaos

## What This Lab Is About

Your app code should never change because config changed. Kubernetes separates configuration from the container using ConfigMaps and Secrets. This lab teaches you every injection method, the failure modes, and the production-grade approach using Workload Identity.

> "A pod that bakes config into its image is a pod that breaks on every environment change."

---

## Concepts Covered

- ConfigMap — non-sensitive key-value config storage
- Secret — base64-encoded sensitive data storage
- Environment Variable Injection — inject config/secrets as env vars
- Volume Mount Injection — inject config/secrets as files
- `CreateContainerConfigError` — what happens when referenced config is missing
- `optional: true/false` — controlling hard vs soft config dependencies
- Workload Identity — federated identity for Pods to access Azure services without credentials

---

## Prerequisites

- kind cluster running (`kind create cluster --name k8s-labs`)
- kubectl installed
- Hands-On 1 and 2 completed

---

## Cluster Setup

```bash
kind create cluster --name k8s-labs
kubectl get nodes
```

---

## Files in This Lab

| File | Purpose |
|---|---|
| `apply-config.yaml` | ConfigMap with non-sensitive app config (db_host, app_port, env) |
| `app-secret.yaml` | Secret with base64-encoded sensitive values (db_password, api_key) |
| `app-pod.yaml` | Pod in `team-a` namespace — injects ConfigMap + Secret as env vars |
| `app-pod-volume.yaml` | Pod in `team-a` namespace — injects ConfigMap as volume mount (files) |
| `app-pod-secret-volume.yaml` | Pod in `team-a` namespace — injects Secret as volume mount (files) |
| `test-pod.yaml` | Broken Pod referencing a non-existent ConfigMap — triggers `CreateContainerConfigError` |

---

## Step-by-Step

### 1. Create Namespace

```bash
kubectl create namespace team-a
```

---

### 2. Create the ConfigMap

```bash
kubectl apply -f apply-config.yaml -n team-a
kubectl get configmap app-config -n team-a
kubectl describe configmap app-config -n team-a
```

**What you observe:** All keys are visible in plaintext. No encryption. Never store passwords here.

**System namespaces for reference:**
- `default` — resources land here if no namespace specified
- `kube-system` — core components: CoreDNS, kube-proxy, CNI
- `kube-public` — readable by all, rarely used
- `kube-node-lease` — node heartbeat tracking
- `local-path-storage` — kind-specific default StorageClass

---

### 3. Create the Secret

```bash
kubectl apply -f app-secret.yaml -n team-a
kubectl get secret app-secret -n team-a
kubectl describe secret app-secret -n team-a
```

**What you observe:** `describe` shows byte sizes only — not values. Compare to ConfigMap which shows plaintext.

**Decode manually to verify:**
```bash
echo "cGFzc3dvcmQxMjM=" | base64 --decode
# Output: password123
```

Base64 is encoding, not encryption. Anyone with the YAML can decode it in seconds.

**Secret type `Opaque` explained:**
Kubernetes doesn't interpret or validate the content — it treats it as raw bytes. Other types (`kubernetes.io/tls`, `kubernetes.io/dockerconfigjson`) have structure Kubernetes understands and validates.

**How to actually secure secrets in production:**

| Approach | What it does |
|---|---|
| Sealed Secrets (Bitnami) | Encrypts with cluster key — safe to commit to Git |
| External Secrets Operator | Secret lives in Azure Key Vault, pulled at runtime — nothing in Git |
| Workload Identity + Key Vault | Pod fetches secret directly via federated token — no K8s Secret at all |
| SOPS + Age/PGP | Encrypts specific fields before committing |

Production standard for AKS: External Secrets Operator or Workload Identity + Key Vault.

---

### 4. Inject ConfigMap + Secret as Environment Variables

```bash
kubectl apply -f app-pod.yaml
kubectl get pod app-pod -n team-a
```

Exec into the pod and verify:
```bash
kubectl exec -it app-pod -n team-a -- sh
echo $DB_HOST
echo $APP_PORT
echo $DB_PASSWORD
exit
```

**What you observe:** Secret value is decoded automatically before injection. Container sees `password123`, not `cGFzc3dvcmQxMjM=`.

**Risk:** Anyone who can `kubectl exec` into this pod can run `printenv` and see all secrets in plaintext.

---

### 5. Inject ConfigMap as Volume Mount

```bash
kubectl apply -f app-pod-volume.yaml
kubectl exec -it app-pod-volume -n team-a -- sh
ls /etc/app/
cat /etc/app/db_host
cat /etc/app/app_port
exit
```

**What you observe:** Each ConfigMap key becomes a file. The filename = key, file content = value.

**Env var vs Volume Mount:**

| | Env Var | Volume Mount |
|---|---|---|
| Use for | Simple config, ports, flags | Config files, certs, multi-line values |
| Secret exposure | `printenv` dumps everything | Only if you `cat` the file |
| Dynamic update | Pod restart required | ConfigMap updates reflect in ~1 min without restart |

---

### 6. Inject Secret as Volume Mount

```bash
kubectl apply -f app-pod-secret-volume.yaml
kubectl exec -it app-pod-secret-volume -n team-a -- sh
ls /etc/secrets/
cat /etc/secrets/db_password
cat /etc/secrets/api_key
exit
```

**What you observe:** Each Secret key becomes a file under `/etc/secrets/`. Values are decoded automatically.

Slightly safer than env var injection — not exposed via `printenv`, but still readable via `cat` by anyone with exec access.

---

### 7. The Pain Exercise — Missing ConfigMap

```bash
kubectl apply -f test-pod.yaml
kubectl get pod test-pod -n team-a
kubectl describe pod test-pod -n team-a
```

**Expected status:** `CreateContainerConfigError`

**Key line in describe output:**
```
MISSING: <set to the key 'something' of config map 'does-not-exist'>  Optional: false
```

**Events section will show:**
```
Warning  Failed  Error: configmap "does-not-exist" not found
```

`Optional: false` = hard dependency. Pod refuses to start if config is missing.

**Make it soft:**
```yaml
configMapKeyRef:
  name: does-not-exist
  key: something
  optional: true
```

Pod starts, `$MISSING` is empty. Use only for non-critical config.

**Production trap:** If a ConfigMap is deleted that a Deployment depends on:
- All new Pods from that Deployment hit `CreateContainerConfigError`
- Existing running Pods are **unaffected until they restart**

**Error comparison:**

| Status | Cause |
|---|---|
| `CreateContainerConfigError` | Referenced ConfigMap or Secret missing |
| `ImagePullBackOff` | Image doesn't exist or registry unreachable |

---

### 8. Cleanup

```bash
kubectl delete pod app-pod -n team-a
kubectl delete pod app-pod-volume -n team-a
kubectl delete pod app-pod-secret-volume -n team-a
kubectl delete pod test-pod -n team-a
kubectl delete namespace team-a
kind delete cluster --name k8s-labs
```

---

## Workload Identity — Concept

**The problem:** Pod needs Azure Key Vault access. Without Workload Identity, you store a Service Principal secret in a K8s Secret → rotates manually → leaks on exec.

**With Workload Identity:** Pod gets a federated token automatically. No credentials stored anywhere.

### The Chain

```
Pod (annotated ServiceAccount)
  → AKS OIDC Issuer (issues federated token)
    → Azure AD (exchanges token for managed identity access)
      → Azure Key Vault (grants access via RBAC)
```

### The YAML

**ServiceAccount:**
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: app-workload-sa
  namespace: team-a
  annotations:
    azure.workload.identity/client-id: "<your-managed-identity-client-id>"
```

**Pod:**
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-pod-wi
  namespace: team-a
  labels:
    azure.workload.identity/use: "true"
spec:
  serviceAccountName: app-workload-sa
  containers:
    - name: app
      image: busybox
      command: ["sh", "-c", "sleep 3600"]
```

### What Happens Internally

| Step | What occurs |
|---|---|
| Pod starts | AKS injects projected volume with federated token |
| App reads token | From `/var/run/secrets/azure/tokens/azure-identity-token` |
| Azure SDK uses token | Exchanges with Azure AD for access token |
| Key Vault access granted | Via Managed Identity RBAC — no password |

**Think of it as:** Managed Identity for Pods. Same concept as a VM's Managed Identity, but scoped to a Kubernetes ServiceAccount federated via OIDC.

Note: Workload Identity requires AKS — not supported on kind local clusters.

---

## Mastery Check

See `QA.md`

---

## What's Next

**Hands-On 5 — Keep Your App Alive and Ready**

Liveness, Readiness, Startup Probes, OOMKilled — teach Kubernetes how to know if your app is healthy.