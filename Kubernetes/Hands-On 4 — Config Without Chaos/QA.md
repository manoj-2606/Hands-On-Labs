# Hands-On 4 — Mastery Check

Answer these without reference. Answers are below each question.

---

**Q1. What is the difference between a ConfigMap and a Secret?**

ConfigMap stores non-sensitive configuration as plaintext key-value pairs. Secret stores sensitive data as base64-encoded values.

Key differences:
- ConfigMap values are visible in plaintext via `kubectl describe`
- Secret values are hidden in `describe` — only byte sizes shown
- Base64 is encoding, not encryption — Secrets are not truly secure without additional tooling (Sealed Secrets, External Secrets, Workload Identity)
- Never store passwords, tokens, or keys in ConfigMaps

---

**Q2. What is Secret type `Opaque` and when would you use a different type?**

`Opaque` = Kubernetes treats the content as raw bytes with no interpretation or validation. It's the default for arbitrary secrets.

Other types exist when Kubernetes needs to understand and validate the structure:
- `kubernetes.io/tls` — for TLS certificates (must have `tls.crt` and `tls.key`)
- `kubernetes.io/dockerconfigjson` — for image pull credentials
- `kubernetes.io/service-account-token` — for ServiceAccount tokens

Use `Opaque` for anything custom: passwords, API keys, connection strings.

---

**Q3. What are the two ways to inject a ConfigMap into a Pod? When do you use each?**

**1. Environment Variable injection:**
```yaml
env:
  - name: DB_HOST
    valueFrom:
      configMapKeyRef:
        name: app-config
        key: db_host
```
Use for: simple values, ports, flags. Easy to read in code via `os.environ`.

**2. Volume Mount injection:**
```yaml
volumeMounts:
  - name: config-vol
    mountPath: /etc/app/
volumes:
  - name: config-vol
    configMap:
      name: app-config
```
Use for: config files, multi-line values, certs. Each key becomes a file under the mount path.

**Critical difference:** Volume mounts update dynamically (~1 min) when ConfigMap changes — no Pod restart needed. Env vars require Pod restart to pick up changes.

---

**Q4. What is `CreateContainerConfigError` and what triggers it?**

The Pod was scheduled and accepted by the node, but the container could not be created because a referenced ConfigMap or Secret does not exist in the same namespace.

Triggered by:
- `configMapKeyRef` pointing to a non-existent ConfigMap
- `secretKeyRef` pointing to a non-existent Secret
- `optional: false` (the default) on the reference

**Production trap:** Only new Pods fail. Existing running Pods are unaffected — until they restart. A deleted ConfigMap can silently break a Deployment's ability to scale or recover.

Diagnose with:
```bash
kubectl describe pod <pod-name> -n <namespace>
# Look at: Environment section and Events section
```

---

**Q5. What is `optional: true` on a ConfigMap or Secret reference? When would you use it?**

Makes the config dependency soft — if the referenced ConfigMap/Secret doesn't exist, the Pod starts anyway and the env var is empty.

```yaml
configMapKeyRef:
  name: feature-flags
  key: dark_mode
  optional: true
```

Use for: non-critical config, feature flags, optional integrations. Never use for database credentials or anything the app cannot function without.

---

**Q6. What problem does Workload Identity solve? How is it different from storing a Service Principal secret in a K8s Secret?**

**With SP secret in K8s Secret:**
- Secret must be created, stored, rotated manually
- Anyone with `kubectl exec` can read it
- If the Secret YAML is committed to Git (even base64), it's compromised

**With Workload Identity:**
- No credentials stored anywhere in the cluster
- Pod's Kubernetes ServiceAccount is federated with an Azure Managed Identity via OIDC
- AKS injects a short-lived token at Pod startup
- Azure AD validates the token and grants scoped access
- Token auto-rotates — no manual rotation

The chain:
```
Pod (annotated ServiceAccount)
  → AKS OIDC Issuer
    → Azure AD
      → Azure Key Vault (via RBAC)
```

Think of it as: the same as a VM's Managed Identity, but for a Pod.

---

**Q7. A Pod is in `CreateContainerConfigError`. The image pulls successfully. What does this tell you?**

The node is reachable, the scheduler worked, kubelet pulled the image — all infrastructure is healthy. The failure is purely at the config layer: a ConfigMap or Secret the container depends on is missing from the namespace.

This is not a node problem. Not a network problem. Not an image problem. Fix: create the missing ConfigMap or Secret in the correct namespace, or set `optional: true` if the config is non-critical.

---

**Q8. Pods can only reference ConfigMaps and Secrets from their own namespace. Why does this matter in practice?**

If you create a ConfigMap in `default` and deploy your Pod in `team-a`, the Pod cannot see that ConfigMap. It will hit `CreateContainerConfigError`.

You must apply config resources to the same namespace as the Pod:
```bash
kubectl apply -f app-config.yaml -n team-a
kubectl apply -f app-secret.yaml -n team-a
```

This is namespace-scoped isolation by design — teams cannot accidentally or maliciously read each other's config across namespace boundaries.