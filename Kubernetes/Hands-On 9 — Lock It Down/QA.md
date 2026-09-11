# Hands-On 9 — Mastery Check

Answer these without reference. Answers are below each question.

---

**Q1. What is a ServiceAccount and why does a pod need one?**

A ServiceAccount is a Kubernetes-native identity assigned to a pod. When a pod makes calls to the Kubernetes API — listing pods, reading secrets, watching deployments — it authenticates using a JWT token automatically mounted at `/var/run/secrets/kubernetes.io/serviceaccount/token`.

Without a ServiceAccount, the pod has no identity the API server can authorize. Every namespace gets a `default` ServiceAccount automatically, but using it is a security risk — it carries no explicit permissions but exists as an attack surface. Always create dedicated ServiceAccounts for each workload with only the permissions that workload needs.

Real-world analogy: ServiceAccount + RBAC = Azure Service Principal + IAM Role. ADO reaches Azure using an SPN. A pod reaches the Kubernetes API using a ServiceAccount token.

---

**Q2. What is the difference between a Role and a ClusterRole?**

| | Role | ClusterRole |
|---|---|---|
| Scope | Single namespace | Entire cluster |
| Can grant access to nodes | No | Yes |
| Can grant cross-namespace access | No | Yes |
| Bound via | RoleBinding | ClusterRoleBinding (or RoleBinding) |

A Role can only grant permissions within the namespace it is created in. A ClusterRole can grant permissions across all namespaces and on cluster-scoped resources like nodes, PersistentVolumes, and StorageClasses — resources that have no namespace.

---

**Q3. What is the difference between a RoleBinding and a ClusterRoleBinding?**

A RoleBinding grants permissions within a single namespace. It can bind either a Role or a ClusterRole — but if it binds a ClusterRole, the permissions are still limited to that namespace.

A ClusterRoleBinding grants permissions cluster-wide. It can only bind a ClusterRole. There is no namespace field on a ClusterRoleBinding.

Key nuance: you can use a ClusterRole with a RoleBinding to reuse a common permission set across namespaces without granting cluster-wide access. This is a common production pattern.

---

**Q4. Why can't a Role grant access to nodes?**

Nodes are cluster-scoped resources — they do not belong to any namespace. A Role is namespace-scoped by definition and can only control access to namespaced resources (pods, services, configmaps, secrets, etc.).

To grant access to nodes, you must use a ClusterRole. Attempting to reference nodes in a Role's rules is technically possible but the binding will never apply because nodes exist outside any namespace context.

---

**Q5. How does a pod authenticate to the Kubernetes API?**

Kubernetes automatically mounts a ServiceAccount token into every pod at:
```
/var/run/secrets/kubernetes.io/serviceaccount/token
```

This is a signed JWT. When the pod makes an API call, it sends this token in the `Authorization: Bearer <token>` header. The API server validates the token, identifies the ServiceAccount, then checks RBAC to determine if the requested action is allowed.

The token is rotated automatically by Kubernetes (expiry set via `expirationSeconds` — default 1 hour). The kubelet handles renewal transparently.

---

**Q6. What does `apiGroups: [""]` mean in a Role?**

The empty string `""` refers to the **core API group** — the original Kubernetes API group that contains the most fundamental resources:

- Pods
- Services
- ConfigMaps
- Secrets
- Namespaces
- Nodes
- PersistentVolumes
- PersistentVolumeClaims

Resources added later (Deployments, ReplicaSets, DaemonSets) live in the `apps` group. Custom Resources live in their own groups (e.g., `networking.k8s.io`, `rbac.authorization.k8s.io`).

Example:
```yaml
rules:
- apiGroups: [""]        # core — pods, services
  resources: ["pods"]
  verbs: ["get", "list"]
- apiGroups: ["apps"]    # apps — deployments, replicasets
  resources: ["deployments"]
  verbs: ["get", "list"]
```

---

**Q7. Why is using the `default` ServiceAccount a security risk?**

Every namespace gets a `default` ServiceAccount automatically. If you don't specify `serviceAccountName` in your pod spec, Kubernetes assigns `default` automatically.

The risk is two-fold:

1. **Blast radius:** If an attacker gains code execution inside any pod using the default ServiceAccount, they inherit whatever permissions that ServiceAccount has — which may be broad if someone accidentally granted cluster-wide permissions to it.

2. **No least privilege:** The default ServiceAccount is shared across all pods in the namespace that don't specify one. A single misconfigured RoleBinding on `default` exposes every pod using it.

Best practice: always create dedicated ServiceAccounts per workload with only the minimum permissions required. Set `automountServiceAccountToken: false` on the default ServiceAccount in every namespace.

---

**Q8. What is the difference between RBAC controlling API access vs node OS access?**

RBAC controls **Kubernetes API calls only** — HTTP requests to the API server (list pods, get nodes, create deployments).

Node OS access — SSH into the underlying Linux machine, running commands on the node filesystem — is entirely separate. That is controlled by SSH keys, cloud IAM (e.g., Azure Bastion, AWS SSM), or node OS user management. RBAC has no influence over it.

A pod with a ClusterRole granting `get nodes` can call `GET /api/v1/nodes` and read node metadata. It cannot SSH into the node, read files on the node's filesystem, or execute commands on the node OS. These are two completely different planes of access.