# Hands-On 9 — Lock It Down

## What This Lab Is About

Every pod in your cluster has an identity. Every API call is authenticated and authorized. RBAC is how you control exactly what each identity can do — and nothing more.

This lab teaches you **least-privilege access control**: ServiceAccounts, Roles, ClusterRoles, and how to verify permissions from inside a running pod.

> Analogy: ServiceAccount + RBAC = ADO Service Principal reaching Azure. The pod authenticates to the Kubernetes API the same way an SPN authenticates to Azure Resource Manager.

---

## Concepts Covered

- ServiceAccounts — pod identity for Kubernetes API calls
- Role — namespace-scoped permissions
- ClusterRole — cluster-wide permissions (nodes, cross-namespace)
- RoleBinding — binds a Role to a ServiceAccount within a namespace
- ClusterRoleBinding — binds a ClusterRole to a ServiceAccount cluster-wide
- Least privilege — grant only what is needed, nothing more

---

## Prerequisites

- kind cluster running (`kind create cluster --name k8s-labs`)
- kubectl installed
- Docker running

---

## Files in This Lab

| File | Purpose |
|---|---|
| `namespace.yaml` | Creates namespace `rbac-lab` |
| `serviceaccount.yaml` | Creates `monitor-sa` — identity for the pod |
| `role.yaml` | `pod-reader` Role — get/list/watch pods in `rbac-lab` only |
| `rolebinding.yaml` | Binds `monitor-sa` to `pod-reader` in `rbac-lab` |
| `pod.yaml` | `monitor-pod` running as `monitor-sa` |
| `clusterrole.yaml` | `node-reader` ClusterRole — get/list/watch pods + nodes cluster-wide |
| `clusterrolebinding.yaml` | Binds `monitor-sa` to `node-reader` cluster-wide |

---

## Step-by-Step

### 1. Create Namespace

```bash
kubectl apply -f namespace.yaml
kubectl get namespaces
```

---

### 2. Create ServiceAccount

```bash
kubectl apply -f serviceaccount.yaml
kubectl get serviceaccount -n rbac-lab
```

> Every namespace has a `default` ServiceAccount. Pods use it if none is specified — this is a security risk. Always create dedicated ServiceAccounts with least-privilege permissions.

---

### 3. Create Role

```bash
kubectl apply -f role.yaml
kubectl describe role pod-reader -n rbac-lab
```

Role grants `get`, `list`, `watch` on pods — scoped to `rbac-lab` namespace only.

> `apiGroups: [""]` = core API group. Pods, Services, ConfigMaps live here. Deployments live in the `apps` group.

---

### 4. Create RoleBinding

```bash
kubectl apply -f rolebinding.yaml
kubectl describe rolebinding monitor-binding -n rbac-lab
```

Connects `monitor-sa` (who) → `pod-reader` (what they can do) in `rbac-lab`.

---

### 5. Deploy Pod Using ServiceAccount

```bash
kubectl apply -f pod.yaml
kubectl get pods -n rbac-lab
```

> `curlimages/curl` (~17MB) — lightweight image with curl to test API calls from inside the pod.

---

### 6. Test RBAC — Role Scope

Exec into the pod:

```bash
kubectl exec -it monitor-pod -n rbac-lab -- /bin/sh
```

Inside the pod:

```sh
TOKEN=$(cat /var/run/secrets/kubernetes.io/serviceaccount/token)

# Should succeed — Role allows this
curl -s -k -H "Authorization: Bearer $TOKEN" \
  https://kubernetes.default.svc/api/v1/namespaces/rbac-lab/pods

# Should return 403 — Role scoped to rbac-lab only
curl -s -k -H "Authorization: Bearer $TOKEN" \
  https://kubernetes.default.svc/api/v1/namespaces/kube-system/pods
```

Expected on kube-system:
```json
{
  "status": "Failure",
  "message": "pods is forbidden: User \"system:serviceaccount:rbac-lab:monitor-sa\" cannot list resource \"pods\" in API group \"\" in the namespace \"kube-system\"",
  "code": 403
}
```

Exit the pod:
```bash
exit
```

---

### 7. Create ClusterRole

```bash
kubectl apply -f clusterrole.yaml
kubectl describe clusterrole node-reader
```

ClusterRole grants read access to pods across all namespaces + nodes (cluster-scoped resource — unreachable via Role).

---

### 8. Create ClusterRoleBinding

```bash
kubectl apply -f clusterrolebinding.yaml
kubectl describe clusterrolebinding monitor-cluster-binding
```

---

### 9. Test RBAC — ClusterRole Scope

```bash
kubectl exec -it monitor-pod -n rbac-lab -- /bin/sh
```

```sh
TOKEN=$(cat /var/run/secrets/kubernetes.io/serviceaccount/token)

# Was FORBIDDEN before — now allowed
curl -s -k -H "Authorization: Bearer $TOKEN" \
  https://kubernetes.default.svc/api/v1/namespaces/kube-system/pods | grep '"name"' | head -5

# Nodes — only possible via ClusterRole
curl -s -k -H "Authorization: Bearer $TOKEN" \
  https://kubernetes.default.svc/api/v1/nodes | grep '"name"'
```

Expected: kube-system pod names + node name returned.

> **Production warning:** ClusterRoleBindings are dangerous. They grant cluster-wide access. Audit them heavily — most workloads should only ever use namespace-scoped Roles.

---

### 10. Cleanup

```bash
kubectl delete -f clusterrolebinding.yaml
kubectl delete -f clusterrole.yaml
kubectl delete -f pod.yaml
kubectl delete -f rolebinding.yaml
kubectl delete -f role.yaml
kubectl delete -f serviceaccount.yaml
kubectl delete -f namespace.yaml
kind delete cluster --name k8s-labs
```

---

## Mastery Check

You have completed this lab if you can answer without reference:

1. What is a ServiceAccount and why does a pod need one?
2. What is the difference between a Role and a ClusterRole?
3. What is the difference between a RoleBinding and a ClusterRoleBinding?
4. Why can't a Role grant access to nodes?
5. How does a pod authenticate to the Kubernetes API?
6. What does `apiGroups: [""]` mean in a Role?
7. Why is using the `default` ServiceAccount a security risk?
8. What is the real-world analogy for ServiceAccount + RBAC?

---

## What's Next

**Hands-On 10 — Route Traffic Like a Pro**

Ingress, NGINX Controller, TLS Termination, Path and Host-based routing. Control how external traffic enters your cluster.