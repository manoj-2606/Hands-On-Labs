# Hands-On 10 — Mastery Check

Answer these without reference. Answers are below each question.

---

**Q1. What is the difference between an Ingress Controller and an Ingress resource?**

They are two completely separate things that work together.

The **Ingress Controller** is the actual software — a running pod inside the cluster (in this lab, NGINX) that acts as a reverse proxy. It watches the Kubernetes API for Ingress resources and configures itself accordingly. It does the actual work of receiving traffic and routing it.

The **Ingress resource** is just a YAML declaration — a set of routing rules you write. It does nothing by itself. It is instructions that the controller reads and enforces.

Analogy: The Ingress resource is like an nginx.conf file. The Ingress Controller is the NGINX process that reads and applies that config. One is data; the other is the engine.

Without a controller, an Ingress resource is dead weight — it sits in etcd but nothing acts on it.

---

**Q2. Why does kind need `extraPortMappings` for Ingress to work?**

Kind runs your entire Kubernetes cluster inside a Docker container. By default, that container is fully isolated — no ports are exposed to your host machine.

`extraPortMappings` punches holes through that isolation:

```yaml
extraPortMappings:
- containerPort: 80
  hostPort: 80
- containerPort: 443
  hostPort: 443
```

This tells Docker: "map port 80 on my laptop to port 80 inside the kind container." Without this, `curl http://localhost/app-a` gets connection refused — your request never enters the cluster.

In real cloud clusters (AKS, EKS, GKE), this is handled automatically by a cloud Load Balancer provisioned when you install the Ingress Controller. The Load Balancer gets a real public IP. Kind has no cloud — so you simulate it with port mappings.

---

**Q3. What does `ingressClassName: nginx` do?**

It tells Kubernetes which Ingress Controller should own and enforce this Ingress resource.

When the NGINX Ingress Controller installs, it registers an `IngressClass` object named `nginx`. Any Ingress resource with `ingressClassName: nginx` is picked up and managed by that controller.

This matters when you have multiple controllers in the same cluster — for example, NGINX for internal traffic and an AWS ALB controller for external traffic. Without `ingressClassName`, the wrong controller might pick up your Ingress, or no controller picks it up at all.

```yaml
spec:
  ingressClassName: nginx  # ← this Ingress belongs to the NGINX controller
```

---

**Q4. What does the `rewrite-target: /` annotation do and why is it needed?**

Without it, a request to `http://localhost/app-a` is forwarded to the backend service as `/app-a` — and the backend app has no route named `/app-a`, so it returns 404.

The annotation strips the matched path prefix before forwarding:

```
Request:  GET /app-a
Matched:  path = /app-a
Forwarded to pod as: GET /   ← rewrite-target strips /app-a
```

This is necessary because `http-echo` (and most real apps) serve their content at `/`, not `/app-a`. The Ingress handles the external-facing path — the app doesn't need to know about it.

In production with more complex apps, `rewrite-target` uses capture groups:

```yaml
nginx.ingress.kubernetes.io/rewrite-target: /$2
```

This lets you strip `/app-a` but preserve the rest of the path — e.g., `/app-a/users/123` becomes `/users/123` at the backend.

---

**Q5. What is TLS termination and why does it matter?**

TLS termination means the Ingress Controller decrypts HTTPS traffic and forwards plain HTTP to backend pods.

```
Client → HTTPS (encrypted) → Ingress Controller → HTTP (plain) → Pod
```

**Why it matters:**

1. **Simplicity** — your app pods don't need TLS logic, certificates, or renewal handling. They receive plain HTTP and stay simple.
2. **Centralized cert management** — one place manages all certificates, not every individual service.
3. **Performance** — TLS handshake overhead is handled once at the edge, not repeated at every internal hop.
4. **Separation of concerns** — security at the network layer, business logic in the app.

In production, cert-manager automates the entire TLS lifecycle — it watches Ingress resources, requests certificates from Let's Encrypt, stores them as Kubernetes Secrets, and rotates them before expiry. You never touch a certificate manually.

---

**Q6. How does the NGINX controller know which TLS certificate to use?**

The Ingress resource declares it explicitly in the `tls` block:

```yaml
spec:
  tls:
  - hosts:
    - localhost
    secretName: ingress-tls
```

The controller reads this, finds the Secret named `ingress-tls` in the same namespace, reads the `tls.crt` and `tls.key` fields, and configures its HTTPS listener with that certificate.

The Secret must be of type `kubernetes.io/tls` and contain exactly two keys: `tls.crt` (the certificate) and `tls.key` (the private key). If the Secret is missing or malformed, the controller falls back to a default self-signed certificate and logs a warning.

---

**Q7. What is the difference between path-based and host-based routing?**

**Path-based routing** — same hostname, different paths route to different backends:

```
myapp.com/api   → api-service
myapp.com/web   → web-service
myapp.com/auth  → auth-service
```

**Host-based routing** — different hostnames route to different backends:

```
api.myapp.com   → api-service
web.myapp.com   → web-service
auth.myapp.com  → auth-service
```

| | Path-based | Host-based |
|---|---|---|
| DNS required | One record | One record per subdomain |
| TLS | One cert for the domain | One cert per subdomain (or wildcard) |
| Separation | Weaker — shared hostname | Stronger — fully independent |
| Production preference | Less common | Standard |

Host-based is preferred in production because each service gets a fully independent entry point — easier to apply different TLS certs, rate limits, and auth policies per host.

---

**Q8. What replaces manual TLS cert management in production?**

**cert-manager** — a Kubernetes controller that automates the full TLS certificate lifecycle.

How it works:
1. You annotate your Ingress with `cert-manager.io/cluster-issuer: letsencrypt-prod`
2. cert-manager detects the annotation, reads the `tls.secretName` from the Ingress
3. It requests a certificate from Let's Encrypt (or any configured issuer)
4. Let's Encrypt validates domain ownership via HTTP-01 or DNS-01 challenge
5. cert-manager stores the issued certificate in the Secret named in `tls.secretName`
6. NGINX Ingress Controller picks up the Secret automatically
7. cert-manager monitors expiry and renews before the cert expires (typically 30 days before)

You never generate, store, or rotate certificates manually. The entire chain is declarative and automated.

---

**Q9. What is an IngressClass and why does it exist?**

An IngressClass is a cluster-scoped Kubernetes resource that registers a controller as a handler for Ingress resources.

Before IngressClass existed (pre-1.18), controllers used annotations to claim Ingress resources — which was messy and inconsistent across vendors. IngressClass standardizes this.

When the NGINX Ingress Controller installs, it creates:

```yaml
apiVersion: networking.k8s.io/v1
kind: IngressClass
metadata:
  name: nginx
spec:
  controller: k8s.io/ingress-nginx
```

Any Ingress with `ingressClassName: nginx` is now owned by this controller. Multiple controllers (NGINX, Traefik, AWS ALB, GCE) can coexist in the same cluster — each managing only their own Ingress resources.

---

**Q10. What happens to traffic flow in production AKS vs kind?**

| Stage | kind | AKS Production |
|---|---|---|
| External entry | `extraPortMappings` on localhost | Azure Load Balancer with public IP |
| Ingress Controller | NGINX pod on control-plane node | NGINX pods on worker nodes |
| TLS certs | Manual self-signed via openssl | cert-manager + Let's Encrypt |
| DNS | `localhost` hardcoded | Real DNS records pointing to LB IP |
| Scaling | Single node | Multiple replicas across nodes |

The Kubernetes resources (Ingress, Service, Deployment) are identical — only the infrastructure underneath changes. That is the power of the abstraction.