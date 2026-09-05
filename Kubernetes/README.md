# Hands-On Kubernetes

A structured, no-fluff, 16-lab Kubernetes mastery roadmap built for engineers with real production experience. Every lab is scenario-driven — you break things intentionally, understand why, and fix them without hand-holding.

> "You don't master Kubernetes by reading. You master it by breaking things intentionally, understanding why they broke, and fixing them."

---

## Who This Is For

- DevOps / Platform Engineers targeting Senior roles
- Engineers preparing for EU/Nordic tech companies
- Anyone who wants to go from "I know kubectl" to "I own the platform"

**Prerequisites:** Docker fundamentals. Basic kubectl familiarity. A working cluster (kind recommended).

---

## Cluster Setup

All labs from Hands-On 1–10 run locally using [kind](https://kind.sigs.k8s.io/). Hands-On 11–16 require AKS or a multi-node cloud cluster.

```bash
# Install kind (Windows)
winget install Kubernetes.kind

# Create cluster
kind create cluster --name k8s-labs

# Verify
kubectl get nodes

# Delete cluster after labs
kind delete cluster --name k8s-labs
```

---

## The 16-Lab Roadmap

| # | Lab | Core Concepts |
|---|-----|---------------|
| 01 | [The Cluster is a Living Organism](https://github.com/manoj-2606/Hands-On-Labs/tree/main/Kubernetes/Hands-On%201%20%E2%80%94%20The%20Cluster%20is%20a%20Living%20Organism) | Pods, Namespaces, Labels, Selectors, Reconciliation Loop |
| 02 | [Give Your App a Safety Net](https://github.com/manoj-2606/Hands-On-Labs/tree/main/Kubernetes/Hands-On%202%20%E2%80%94%20Give%20Your%20App%20a%20Safety%20Net) | Deployments, ReplicaSets, Rolling Updates, Rollback, Resource Limits |
| 03 | [Make Your App Discoverable](https://dev.azure.com/manojmanojkumar2513/_git/Hands-On-Labs?path=/Kubernetes/Hands-On%203%20%E2%80%94%20Make%20Your%20App%20Discoverable) | Services, CoreDNS, Endpoints, kube-proxy |
| 04 | [Config Without Chaos](https://dev.azure.com/manojmanojkumar2513/_git/Hands-On-Labs?path=/Kubernetes/Hands-On%204%20%E2%80%94%20Config%20Without%20Chaos) | ConfigMaps, Secrets, Volume Mounts, Workload Identity |
| 05 | [Keep Your App Alive and Ready](https://dev.azure.com/manojmanojkumar2513/_git/Hands-On-Labs?path=/Kubernetes/Hands-On%205%20%E2%80%94%20Keep%20Your%20App%20Alive%20and%20Ready) | Liveness, Readiness, Startup Probes, OOMKilled |
| 06 | Stateful Apps Are a Different Beast | StatefulSets, PVCs, StorageClass, Headless Services, Init Containers |
| 07 | One Pod Per Node, No Exceptions | DaemonSets, Taints, Tolerations, Node Affinity, Pod Anti-Affinity |
| 08 | Scale or Die | HPA, Metrics Server, KEDA concept, Load Testing |
| 09 | Lock It Down | RBAC, ServiceAccounts, Roles, ClusterRoles, Workload Identity |
| 10 | Route Traffic Like a Pro | Ingress, NGINX Controller, TLS Termination, Path/Host Routing |
| 11 | Networking Internals — No Magic | CNI, kube-proxy, iptables, NetworkPolicy, CoreDNS internals |
| 12 | Jobs, Cron, and Batch | Jobs, CronJobs, Parallel Processing, Sidecar Pattern |
| 13 | Helm — Package Your Platform | Helm Charts, Templating, Multi-env Deployments, Rollback |
| 14 | Observe Everything | Prometheus, Grafana, ServiceMonitor, PromQL, Alerting |
| 15 | GitOps — The Cluster Manages Itself | ArgoCD, Drift Detection, Auto-sync, App of Apps |
| 16 | Harden, Secure, and Operate Production | Kyverno, Trivy, Pod Security Standards, Azure Key Vault, DR |

---

## Stack Covered

| Layer | Tools |
|---|---|
| Orchestration | Kubernetes |
| Package Management | Helm |
| GitOps | ArgoCD |
| Monitoring | Prometheus + Grafana |
| Security | Kyverno, Trivy, Pod Security Standards |
| Secrets | Azure Key Vault + Secrets Store CSI |
| Networking | CNI, NGINX Ingress, CoreDNS, NetworkPolicy |
| Autoscaling | HPA, Metrics Server |

---

## Repo Structure

```
Hands-On-Labs/
└── Kubernetes/
    ├── Hands-On 1 — The Cluster is a Living Organism/
    │   ├── README.md
    │   ├── namespace-team-a.yaml
    │   ├── namespace-team-b.yaml
    │   ├── pod-team-a.yaml
    │   ├── pod-team-b.yaml
    │   └── pod-broken.yaml
    ├── Hands-On 2 — Give Your App a Safety Net/
    └── ...
```

---

## Philosophy

Each lab is designed around a **real production scenario** — not toy examples. You will:

- Deploy broken things on purpose
- Read events, not just logs
- Understand the control plane's decision-making
- Leave each lab with permanent muscle memory

No shortcuts. No magic. Just scars that teach.