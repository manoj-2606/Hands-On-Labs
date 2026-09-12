# Hands-On 11 — Mastery Check

Answer these without reference. Answers are below each question.

---

**Q1. What is CNI and what three things does it do when a pod starts?**

CNI (Container Network Interface) is the plugin layer responsible for pod networking. Every time a pod starts, the CNI plugin does three things:

1. **Assigns an IP** to the pod from the node's allocated subnet
2. **Creates a veth pair** — a virtual ethernet cable connecting the pod's network namespace to the node
3. **Writes cross-node routes** on the node so other nodes know how to reach this node's pod subnet

Without CNI, pods would have no IPs and no connectivity. kind uses `kindnet` as its CNI. Production clusters commonly use Calico, Cilium, or (on AKS) Azure CNI.

---

**Q2. What is a veth pair and where are its two ends?**

A veth pair is a virtual ethernet cable — a pair of linked network interfaces where traffic entering one end exits the other.

- **One end lives inside the pod** — visible as `eth0` inside the pod's network namespace
- **Other end lives on the node** — visible as `vethXXXXXXXX` (e.g., `veth2ff9b60f`) in the node's network namespace

When you run `ip route` on the node, you see entries like `10.244.2.2 dev veth2ff9b60f scope host` — that's the node's direct link to pod-a via the veth pair. CNI creates this pair automatically when the pod starts and tears it down when the pod dies.

---

**Q3. Why does pod-a have no route for pod-b's subnet in its own routing table?**

Pod-a's routing table only knows:
- Its own IP (`10.244.2.2`)
- Its node's gateway (`10.244.2.1`)
- A default route for everything else → send to the gateway

Pod-a doesn't need to know how to reach `10.244.1.0/24` (pod-b's subnet). It just sends unknown traffic to its default gateway — the node. The **node's routing table** has the cross-node route (`10.244.1.0/24 via 172.18.0.3`) written by CNI. The pod delegates all cross-node routing decisions to the node.

This is by design — pods stay simple. The CNI-managed node routing table handles all inter-node traffic.

---

**Q4. What is a ClusterIP and where does it actually exist?**

A ClusterIP is a virtual IP assigned to a Service. It does **not** exist on any real network interface, any pod, or any node. No machine in the cluster "owns" it.

It exists only as a **NAT rule in the kernel** — written by kube-proxy into the `KUBE-SERVICES` nftables chain on every node. When a packet is sent to the ClusterIP, the kernel intercepts it at the nftables layer and rewrites the destination to the actual pod IP (DNAT) before the packet ever leaves the node.

```
10.96.225.205:80  →  (nftables DNAT)  →  10.244.2.2:8080
(ClusterIP)                               (real pod IP)
```

If you `ping` a ClusterIP, it may not respond — there's no host to reply at the ICMP level. But TCP connections work because kube-proxy's rules handle the translation.

---

**Q5. What chain does kube-proxy write Service NAT rules into?**

`KUBE-SERVICES` — a chain in the `nat` table, managed by kube-proxy (via iptables or nftables backend depending on the kernel version).

Every Service gets a rule in `KUBE-SERVICES` that matches on destination IP + port and jumps to a per-Service chain (e.g., `KUBE-SVC-XXXXX`) which then randomly selects a backend endpoint (pod) and DNATs to it.

On newer kernels (like kind v1.37.0), kube-proxy uses the nftables backend — rules live in `nft list ruleset` under `KUBE-SERVICES`, not in legacy `iptables -t nat -L`.

---

**Q6. What is CoreDNS and what IP does it run on in this lab?**

CoreDNS is the cluster-internal DNS server — a Deployment running in `kube-system`. It is responsible for resolving Kubernetes Service names to their ClusterIPs.

In this lab it ran at **`10.96.0.10`** — visible in `/etc/resolv.conf` inside every pod as the `nameserver` entry. This IP is itself a ClusterIP (a Service in `kube-system` named `kube-dns`).

When a pod does `nslookup service-a`, the query goes to `10.96.0.10`. CoreDNS looks up the Service in its internal records (synced from the Kubernetes API) and returns the ClusterIP. It does not do recursive external resolution itself — it forwards unknown names upstream to the node's DNS.

---

**Q7. What does `ndots:5` mean and how does it affect external DNS resolution?**

`ndots:5` is a resolver option in `/etc/resolv.conf`. It means: if the hostname has **fewer than 5 dots**, try appending each search domain before attempting the name as-is.

**Effect on cluster-internal names:**
`curl service-a` → 0 dots → tries `service-a.net-lab.svc.cluster.local` → resolves immediately → done.

**Effect on external names:**
`curl google.com` → 1 dot → tries all search domains first:
1. `google.com.net-lab.svc.cluster.local` → NXDOMAIN
2. `google.com.svc.cluster.local` → NXDOMAIN
3. `google.com.cluster.local` → NXDOMAIN
4. Finally tries `google.com` → resolves externally

This causes 3 extra DNS queries for every external hostname lookup from inside a pod. In latency-sensitive apps, this can be tuned by using FQDNs (trailing dot: `google.com.`) or reducing `ndots` via pod `dnsConfig`.

---

**Q8. What does `podSelector: {}` select in a NetworkPolicy?**

An empty `podSelector: {}` selects **all pods** in the namespace where the NetworkPolicy is applied.

```yaml
spec:
  podSelector: {}   # ← matches every pod in the namespace
  policyTypes:
  - Ingress
  - Egress
```

Combined with no `ingress` or `egress` rules, this creates a blanket deny — no pod in the namespace can send or receive any traffic. This is the standard "default deny" baseline in production — you apply this first, then selectively open only what's needed.

---

**Q9. Why does NetworkPolicy require both egress on the sender AND ingress on the receiver?**

NetworkPolicy is enforced at both ends independently. A policy on pod-b allowing ingress from pod-a only opens pod-b's "door" — it doesn't open pod-a's "door" to send.

```
pod-a  →  [egress policy on pod-a]  →  [ingress policy on pod-b]  →  pod-b
```

Both gates must be open for traffic to flow. If only ingress on pod-b is allowed but pod-a has no egress allow, traffic is dropped at pod-a's egress before it even reaches the network.

This is intentional — it gives teams independent control. The team owning pod-b controls who can talk to it (ingress). The team owning pod-a controls where it can send (egress). Neither can unilaterally open a path — both must agree.

---

**Q10. Why doesn't NetworkPolicy work in kind by default?**

kind's default CNI is **kindnet** — a minimal CNI that handles pod IP assignment and cross-node routing but **does not implement NetworkPolicy enforcement**.

NetworkPolicy enforcement is a CNI responsibility, not a Kubernetes core responsibility. Kubernetes only stores the NetworkPolicy objects — it's the CNI plugin that reads them and programs the kernel (via iptables, nftables, eBPF) to drop or allow packets accordingly.

kindnet has no such logic. The NetworkPolicy objects exist in etcd, kubectl shows them applied, but no enforcement happens at the packet level.

**In production:**
- AKS with **Calico** or **Cilium** enforces NetworkPolicy correctly
- Cilium also supports advanced L7 policies (HTTP path-level, gRPC method-level) beyond what standard NetworkPolicy offers
- Always verify your CNI supports NetworkPolicy before relying on it for security

---

**Q11. What is the difference between kindnet (kind's CNI) and Calico/Cilium?**

| | kindnet | Calico | Cilium |
|---|---|---|---|
| Pod IP assignment | ✅ | ✅ | ✅ |
| Cross-node routing | ✅ | ✅ | ✅ |
| NetworkPolicy enforcement | ❌ | ✅ | ✅ |
| L7 policy (HTTP/gRPC) | ❌ | ❌ | ✅ |
| eBPF dataplane | ❌ | Optional | ✅ (default) |
| Production use | No | Yes | Yes |

kindnet is intentionally minimal — it exists to make kind clusters fast to spin up for development and testing, not for production security.

---

**Q12. What happens end-to-end when pod-a runs `curl service-a`?**

Full chain, no skipping:

1. `curl service-a` triggers DNS resolution
2. Pod's resolver checks `/etc/resolv.conf` — `ndots:5`, nameserver `10.96.0.10`
3. `service-a` has 0 dots → append first search domain → `service-a.net-lab.svc.cluster.local`
4. Query sent to CoreDNS at `10.96.0.10`
5. CoreDNS returns `10.96.225.205` (the ClusterIP)
6. `curl` opens TCP connection to `10.96.225.205:80`
7. Packet hits the node's nftables `KUBE-SERVICES` chain
8. Rule matches `10.96.225.205:80` → DNAT → `10.244.2.2:8080` (pod-a's real IP)
9. Node routes packet to `10.244.2.2` via veth pair
10. Pod-a receives the request on port 8080

```
curl service-a
  → CoreDNS → 10.96.225.205
  → nftables DNAT → 10.244.2.2:8080
  → veth → pod-a
```