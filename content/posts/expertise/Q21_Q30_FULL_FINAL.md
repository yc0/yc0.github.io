---
date: '2025-12-04T19:51:15+08:00'
draft: true
categories:
  - Performance
title: Kubernetes CNI
---
# Batch Q21–Q30 Final Deep Version (with Follow-up Answers + PlantUML)

## Q21. Kubernetes CNI（Calico/Flannel/Cilium）差異與排查方法

### Standard Answer
CNI 負責 Pod 與 Pod 之間的網路連線；Calico 主要用 BGP/IPIP/VXLAN 做 L3 routing，Flannel 用 VXLAN/host-gw 提供簡單 overlay，Cilium 則用 eBPF 實作高效 dataplane 與 L3–L7 貼合的 NetworkPolicy。

### Advanced Answer
Calico:
- 模式：BGP / IPIP / VXLAN
- 特性：純 L3 routing，支援 NetworkPolicy，scale 大
- 常見場景：multi-node / multi-rack 大集群

Flannel:
- 模式：VXLAN 為主
- 特性：只提供 Pod CIDR 連通，不含 L3 policy
- 常見場景：中小型集群、demo

Cilium:
- 模式：eBPF/XDP + BPF map
- 特性：高性能，支援 L7-aware policy、觀察性、Hubble
- 常見場景：需要高性能與 service mesh 整合

#### 排查 Pod-to-Pod unreachable 實例
```bash
kubectl exec -it pod-a -- ping 10.244.x.y
ip route
kubectl get ds -n kube-system
kubectl logs -n kube-system -l k8s-app=calico-node
kubectl logs -n kube-system -l k8s-app=cilium
```

### PlantUML — CNI datapath（抽象示意）
{{< plantuml >}}
@startuml
node "Node A" {
  node "Pod A" --> "veth A"
  "veth A" --> "CNI BPF Layer"
}
"CNI BPF Layer" --> "Underlay Network"
"Underlay Network" --> "CNI BPF Layer Node B"
node "Node B" {
  "CNI BPF Layer Node B" --> "veth B"
  "veth B" --> "Pod B"
}
@enduml
{{< /plantuml >}}

### Follow-up Answers
Calico BGP 比 OSPF 更適合 DC 規模的 overlay，因為 BGP 可透過 route reflector 與 policy 貼合 multi-tenant；Cilium 透過 eBPF 減少 iptables rule 掃描，大幅提升效能。


## Q22. Kubernetes NodePort / ClusterIP / LoadBalancer 差異與流量路徑

### Standard Answer
ClusterIP 只在 Cluster 內可達；NodePort 會在每個 Node 上開一個高位 port；LoadBalancer 串接雲端 LB，對外暴露 service。

### Advanced Answer
典型流量路徑：
Client → Cloud LB → NodePort → kube-proxy → Pod

### PlantUML — NodePort 流程
{{< plantuml >}}
@startuml
actor Client
rectangle "Cloud LB" as LB
node "K8s Node" as Node
rectangle "kube-proxy" as KP
node "Pod"

Client -> LB : TCP/HTTPS
LB -> Node : NodePort
Node -> KP : DNAT
KP -> Pod : Forward
@enduml
{{< /plantuml >}}

### Follow-up Answers
NodePort 架構中，DNAT 加上 conntrack 可能在 backend Pod 重建後仍保留指向舊 IP 的 entry，造成 connection reset。


## Q23. Service Mesh（Istio）流量導向與排錯方法

### Standard Answer
Istio 透過 Envoy sidecar 接管 inbound/outbound 流量，實現 routing、mTLS 與 observability。

### Advanced Answer
常用排查：
```bash
istioctl proxy-status
istioctl pc clusters <pod>.<ns>
istioctl pc routes <pod>.<ns>
```

### PlantUML — Istio Sidecar Path
{{< plantuml >}}
@startuml
actor Client
node "Client Pod" {
  [App A] --> [Envoy Sidecar A]
}
node "Server Pod" {
  [Envoy Sidecar B] --> [App B]
}
Client -> [App A]
[App A] -> [Envoy Sidecar A]
[Envoy Sidecar A] -> [Envoy Sidecar B] : mTLS
[Envoy Sidecar B] -> [App B]
@enduml
{{< /plantuml >}}

### Follow-up Answers
Istio 冷啟動慢，多半是 sidecar 注入與 xDS 同步延遲，可透過調整 readinessProbe 與 preStop hook 減少影響。


## Q24. Kubernetes DNS（CoreDNS）效能瓶頸排查

### Standard Answer
CoreDNS QPS 過高或 search domain 過多會導致 DNS latency。

### Advanced Answer
```bash
kubectl logs -n kube-system -l k8s-app=kube-dns
kubectl top pod -n kube-system
cat /etc/resolv.conf
```

### PlantUML — DNS Query Flow
{{< plantuml >}}
@startuml
node "Pod" as Pod
node "CoreDNS" as DNS
node "Upstream" as Up

Pod -> DNS : Query
DNS -> Up : Forward
Up -> DNS : Answer
DNS -> Pod : Response
@enduml
{{< /plantuml >}}

### Follow-up Answers
search domain 會讓簡短名稱被多次嘗試不同 FQDN，若上游 DNS 慢，整體查詢延遲會線性疊加。


## Q25. Kubernetes Storage（CSI）I/O latency 排查

### Standard Answer
檢查 PVC/PV、CSI driver log、底層磁碟 IOPS 與 throughput 是否打滿。

### Advanced Answer
```bash
kubectl get pvc,pv
kubectl describe pvc <pvc>
kubectl logs -n kube-system -l app=csi
iostat -x 1 5
```

### PlantUML — CSI Flow
{{< plantuml >}}
@startuml
actor User
node "Kubernetes" {
  [Pod] --> [kubelet]
  [kubelet] --> [CSI Driver] : NodePublishVolume
}
node "Storage Backend" as SB
[CSI Driver] -> SB : Provision/Attach
SB --> [CSI Driver] : OK
[CSI Driver] --> [kubelet] : Mount
@enduml
{{< /plantuml >}}

### Follow-up Answers
慢多半是 storageClass 選錯（如 HDD / PD-standard），需改 SSD/Hyperdisk 或放大磁碟 size 拉高 baseline IOPS。


## Q26. Kubernetes HPA（Horizontal Pod Autoscaler）抖動排查

### Standard Answer
HPA 容易因為 metrics 波動或目標 utilize 太低而頻繁 scale-in/out。

### Advanced Answer
```bash
kubectl describe hpa <name>
kubectl top pod
```

### PlantUML — HPA Path
{{< plantuml >}}
@startuml
node "Metrics Server" as MS
node "HPA Controller" as HPA
node "API Server" as API
node "Deployment" as Dep
node "Pods" as Pods

MS -> HPA : metrics
HPA -> API : scale request
API -> Dep : update replicas
Dep -> Pods : create/terminate
@enduml
{{< /plantuml >}}

### Follow-up Answers
可透過 stabilizationWindow、multiple metrics、避免使用單一瞬時 CPU 指標來降低抖動。


## Q27. readiness/liveness 設置錯誤造成 cascading failure

### Standard Answer
readiness 設太嚴會讓服務在短暫抖動時整體被標記為不健康，造成 cascading failure。

### Advanced Answer
```bash
kubectl describe pod <pod>
```

### PlantUML — Cascading Failure
{{< plantuml >}}
@startuml
actor Client
node "Service" {
  [Pod A]
  [Pod B]
  [Pod C]
}
Client -> "Service"
"Service" --> [Pod A] : traffic
[Pod A] -> "Service" : readiness fail
"Service" --> [Pod B] : more traffic
[Pod B] -> "Service" : overload
"Service" --> [Pod C] : all traffic
[Pod C] -> "Service" : crash
@enduml
{{< /plantuml >}}

### Follow-up Answers
readiness 應容忍短秒級 jitter，liveness 則應只在程式 irrecoverable 時才重啟，否則會放大問題。


## Q28. Node NotReady / Kubelet Unhealthy 排查

### Standard Answer
Node NotReady 通常與 kubelet crash、runtime 問題或 DiskPressure/MemoryPressure 有關。

### Advanced Answer
```bash
kubectl describe node <node>
journalctl -u kubelet -xe
systemctl status containerd
df -h
du -sh /var/lib/containerd /var/lib/kubelet
```

### PlantUML — Node Health
{{< plantuml >}}
@startuml
node "Node" {
  [kubelet] --> [container runtime]
}
[kubelet] -> "API Server" : NodeStatus
"API Server" -> "Scheduler" : Node Ready/NotReady
@enduml
{{< /plantuml >}}

### Follow-up Answers
DiskPressure 通常由 image/cache/log 滿造成，需清理與調整 log rotation。


## Q29. Ingress 504 疑難排查（Upstream timeout）

### Standard Answer
504 表示 Ingress/LB 等待 upstream 過久。需確認是 LB 還是 Ingress 吐 504，再檢查 backend latency 或 timeout 設定。

### Advanced Answer
```bash
kubectl logs -n ingress-nginx deploy/ingress-nginx-controller | grep 504
kubectl exec -it <pod> -- curl -v http://svc:port/path
```

### PlantUML — 504 Path
{{< plantuml >}}
@startuml
actor Client
rectangle "Load Balancer" as LB
rectangle "Ingress" as IG
rectangle "Service" as S
rectangle "Pod" as P

Client -> LB
LB -> IG
IG -> S
S -> P : slow response
IG -> Client : 504 Gateway Timeout
@enduml
{{< /plantuml >}}

### Follow-up Answers
從 LB log（如 GCP LB 的 backend_timeout）與 Ingress log（upstream timed out）可以區分是哪一層 timeout。


## Q30. CNI Crash 導致全網中斷的根因分析

### Standard Answer
CNI DaemonSet crash 會使新 Pod 無法正確建立 veth/route，甚至讓既有 Pod 的 routing 失效。

### Advanced Answer
```bash
kubectl get ds -n kube-system
kubectl logs -n kube-system -l k8s-app=calico-node
kubectl logs -n kube-system -l k8s-app=cilium
ip addr
ip route
```

### PlantUML — CNI Failure
{{< plantuml >}}
@startuml
node "Node" {
  [kubelet] as K
  [CNI Daemon] as CNI
  [Pod] as P
}
K -> CNI : ADD/DEL Pod
CNI -> P : setup veth/route
CNI -x P : crash => route broken
@enduml
{{< /plantuml >}}

### Follow-up Answers
calico-node/cilium-agent 掌管全 node veth 和 route，一旦 crash/升級失敗，node 上 Pod 的 east-west traffic 可能全部中斷。
