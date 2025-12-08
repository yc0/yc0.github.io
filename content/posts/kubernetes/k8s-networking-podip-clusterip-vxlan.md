---
date: '2025-12-04T00:00:00+08:00'
draft: true
categories:
  - kubernetes
  - fundamental
title: Kubernetes 內部網路、Pod IP、ClusterIP、VXLAN 與雲端 CNI 全整理
---
主題：Pod 彼此怎麼找到對方？Service 怎麼導流？什麼時候需要 VXLAN？為什麼雲端多半不用 VXLAN？
---

## 1. 核心觀念總覽

1. **每個 Pod 有獨立 IP**（Pod IP），由 **CNI Plugin** 分配。
2. 每個 Node 通常會分到一段 **PodCIDR**（例如：`10.244.1.0/24`）。
3. Kubernetes 內部通訊的兩種主要方式：  
   - **直接透過 Pod IP 通訊**（Pod ↔ Pod）  
   - **透過 Service 的 ClusterIP 間接找到 Pod**（Pod → Service → Pod）
4. **kube-proxy** 負責維護 Service 的「虛擬 IP（ClusterIP）」與負載平衡規則（iptables / IPVS）。
5. **CNI Plugin** 負責：
   - 在 Node 上建立 veth/bridge 等虛擬網路
   - 在 Node 與 Node 之間建立 **L3 路由或 Overlay（VXLAN 等）**
6. **VXLAN** 是一種 Overlay 技術，用來在「實體網路不願意/不能幫你路由 PodCIDR」時，自己建一層虛擬網路。
7. 雲端（AWS / GCP / Azure）多半不用 VXLAN，因為 **Pod IP 就是 VPC/VNet 內的原生可路由 IP**。

---

## 2. Pod-to-Pod 通訊基本原理

### 2.1 同一個 Node 上的 Pod 通訊（簡化版）

1. Pod A 與 Pod B 在同一個 Node。
2. 兩個 Pod 各自有 veth pair 連到 Node 上的 bridge（例如 `cni0`）。
3. Pod A 打 Pod B 的 Pod IP，封包進入 veth → bridge → veth → Pod B。  
   不需要跨 Node 也不需要 VXLAN。

> 同 Node 情境其實就像同一台 Linux 機器上兩個 namespace 透過 bridge 溝通。

### 2.2 跨 Node 通訊的抽象模型（不管有沒有 VXLAN）

只要滿足：

> **「每個 PodCIDR 在整個集群內可被路由」**

那 Pod A（在 Node1）就可以打到 Pod B（在 Node2）。

實作方法有兩種：

1. **純 L3 routing（不需要 VXLAN）**
2. **Overlay（VXLAN 封裝）**

下面先用「抽象流程」表示 Pod A → Pod B：

{{< plantuml >}}
@startuml
title Pod A -> Pod B 跨 Node 通訊抽象流程

node "Node1" {
  rectangle "Pod A 10.244.1.5" as PodA
  rectangle "CNI Bridge (veth / cni0)" as CNI1
}

cloud "Underlay / Network Fabric" as NET

node "Node2" {
  rectangle "CNI Bridge (veth / cni0)" as CNI2
  rectangle "Pod B 10.244.2.8" as PodB
}

PodA --> CNI1 : 發送封包
Dst=10.244.2.8
CNI1 --> NET : 根據路由轉送
(10.244.2.0/24)
NET --> CNI2 : 封包抵達 Node2
CNI2 --> PodB : 投遞封包給 Pod B

@enduml
{{< /plantuml >}}

這個抽象圖不管底下是「Routing」還是「VXLAN Overlay」，流程都適用。

---

## 3. Pod IP / ClusterIP 定義與比較

### 3.1 Pod IP 定義（技術版）

- 由 **CNI Plugin** 分配的 **真實、可路由 IP**（在 Kubernetes cluster 範圍內）。
- 每個 Pod 有自己的 IP，生命周期 = Pod 的生命周期。
- 通常來自每個 Node 的 PodCIDR：
  - Node1：`10.244.1.0/24`
  - Node2：`10.244.2.0/24`
- Pod-to-Pod 的底層通訊，最終都是打到對方的 **Pod IP**。

> ✅ 可以記作：**「Pod IP = CNI 管的實體 L3 IP（在 cluster 中）」**。

---

### 3.2 ClusterIP 定義（技術版）

- **Service 的虛擬 IP（VIP）**，不綁在任何實體網路卡上。
- 由 kube-apiserver 分配，**kube-proxy** 利用 iptables / IPVS 實作：
  - 接到 ClusterIP:Port 的封包
  - 根據規則選擇一個 backend Pod（Pod IP）
  - 做 DNAT（目的 IP/Port 改成 Pod IP/Port）
- 只在 Cluster 內使用，外部無法直接存取（需 NodePort / LoadBalancer / Ingress）。

> ✅ 可以記作：**「ClusterIP = Service 的虛擬入口，由 kube-proxy NAT 到 Pod IP」**。

---

### 3.3 Pod IP vs ClusterIP 比較表

| 項目           | Pod IP                                  | ClusterIP                                          |
|----------------|------------------------------------------|----------------------------------------------------|
| 類型           | 真實 IP（CNI 分配）                     | 虛擬 IP（Service VIP）                            |
| 發配者         | CNI Plugin                              | kube-apiserver 分配，kube-proxy 實作              |
| 壽命           | 跟 Pod 一樣                             | 跟 Service 一樣                                    |
| 用途           | Pod ↔ Pod 通訊                          | Pod → Service → Pod（負載平衡）                   |
| 是否 NAT       | 不一定（同 Node 通常不用）              | 必須 DNAT 成後端 Pod IP                           |
| 對外可見性     | 無法被外部直接訪問                      | 不能直接被外部訪問（需 NodePort/LB/Ingress）      |
| 負載平衡能力   | 無                                       | 具備（由 kube-proxy / IPVS 等實現）               |
| 作業層級       | L3 Routing                               | L4 Proxy / VIP + DNAT                             |

---

### 3.4 Pod A → Service（ClusterIP）→ Pod B 流程圖（PlantUML）

{{< plantuml >}}
@startuml
title Pod A -> Service(ClusterIP) -> Pod B 流程

node "Node1" {
  rectangle "Pod A 10.244.1.5" as PodA
  rectangle "kube-proxy (iptables/IPVS)" as KP1
}

rectangle "CoreDNS" as DNS

node "Node2" {
  rectangle "Pod B 10.244.2.8" as PodB
}

database "Service ClusterIP: 10.96.0.10:80" as SVC

PodA --> DNS : 查詢 backend-svc
FQDN -> ClusterIP
DNS --> PodA : 回傳 10.96.0.10

PodA --> KP1 : 封包 Dst=10.96.0.10:80
KP1 --> SVC : 匹配 Service 規則
SVC --> KP1 : 選擇一個後端 Pod IP (例如 10.244.2.8:8080)

KP1 --> PodB : DNAT 後轉送封包 Dst=10.244.2.8:8080

@enduml
{{< /plantuml >}}

---

## 4. L3 Routing vs VXLAN Overlay

### 4.1 純 Routing（不使用 VXLAN）：概念

假設：

- PodCIDR：`10.244.0.0/16`
- Node1：`10.244.1.0/24`
- Node2：`10.244.2.0/24`

若 **實體網路願意幫你路由這些 PodCIDR**，可以這樣做：

- 中央 Router 或各 Node 上 routing table 有：

```text
10.244.1.0/24 via Node1_IP
10.244.2.0/24 via Node2_IP
```

CNI（例如 Calico BGP / Flannel host-gw）幫你自動寫好這些路由，封包就像普通 L3 網路一樣在 Node 之間轉送，完全不需要封裝。

### 4.2 只用 Routing 的流程圖（不含 VXLAN）

{{< plantuml >}}
@startuml
title L3 Routing：跨 Node Pod 通訊（不使用 VXLAN）

node "Node1" {
  rectangle "Pod A 10.244.1.5" as PodA
  rectangle "CNI Bridge" as CNI1 node "Node1 OS" as OS1
}

node "Core Router" as CR

node "Node2" {
  rectangle "CNI Bridge" as CNI2
  rectangle "Pod B 10.244.2.8" as PodB
  node "Node2 OS" as OS2
}

PodA --> CNI1 : Dst=10.244.2.8
CNI1 --> OS1 : 查詢路由表 10.244.2.0/24 via CR
OS1 --> CR : 送往 Core Router
CR --> OS2 : 轉送到 Node2
OS2 --> CNI2 : 交給 CNI bridge
CNI2 --> PodB : 投遞封包

@enduml
{{< /plantuml >}}

> 這種模式依賴「實體網路（Router）願意幫你管理 PodCIDR」。  
> 常見實作：**Calico BGP 模式**、**Flannel host-gw**。

---

## 5. VXLAN Overlay：什麼時候需要？怎麼運作？

### 5.1 為什麼需要 VXLAN？

在很多 On-Prem / 傳統企業網路中：

1. 網路管理員 **不願意幫你新增一堆 PodCIDR 路由**。
2. 企業既有的 10.x/172.x/192.168.x 網段已經被大量使用，PodCIDR 容易撞網段。
3. 不允許你在核心網路上跑 BGP 給 Kubernetes。
4. 不希望 Kubernetes 的變動影響實體網路設備。

> 這時：**PodCIDR 在實體網路「實務上」不會被 route** → 只能靠 Overlay 自己解決。  
> VXLAN 就是最常見的解法之一。

---

### 5.2 VXLAN 的基本概念

- **L2 over L3**：把原本的 Ethernet Frame 再包在 UDP 封包內傳輸。
- 每條 Overlay Network 用一個 **VNI（VXLAN Network Identifier）** 區分。
- Kubernetes CNI（Flannel / Calico / Cilium 的 VXLAN 模式）會：
  - 在每個 Node 建立虛擬介面（如 `flannel.1` / `cilium_vxlan`）
  - 在 Node 與 Node 之間透過 VXLAN Tunnel 傳 Pod 封包
  - 實體網路只看到 NodeIP ↔ NodeIP 的 UDP 封包。

> ✅ 可以記作：**「VXLAN = Kubernetes 自己在 Node 之間做一層虛擬交換器」**。

---

### 5.3 使用 VXLAN 的封包路徑（Pod A → Pod B）

1. Pod A 打 Pod B 的 Pod IP（`10.244.2.8`）。  
2. Node1 的 routing table：
   - `10.244.2.0/24 dev flannel.1`
3. 封包從 CNI bridge 進 `flannel.1` → **被 VXLAN 封裝**：
   - Outer SrcIP = Node1_IP
   - Outer DstIP = Node2_IP
   - UDP SrcPort/ DstPort（預設 8472 等）
4. 實體網路只處理 Node1_IP → Node2_IP 的 UDP 流量。
5. Node2 收到 VXLAN 封包 → 解封裝 → 還原原始 Pod 封包。
6. 再透過 CNI bridge 投遞到 Pod B。

### 5.4 VXLAN Overlay 的流程圖（PlantUML）

{{< plantuml >}}
@startuml
title VXLAN Overlay：Pod A -> Pod B 跨 Node 通訊

node "Node1" {
  rectangle "Pod A 10.244.1.5" as PodA
  rectangle "CNI Bridge (cni0)" as CNI1
  rectangle "VXLAN IF flannel.1 / cilium_vxlan" as VX1
}

cloud "Underlay Network (實體 L3 網路)" as Underlay

node "Node2" {
  rectangle "VXLAN IF flannel.1 / cilium_vxlan" as VX2
  rectangle "CNI Bridge (cni0)" as CNI2
  rectangle "Pod B 10.244.2.8" as PodB
}

PodA --> CNI1 : Dst=10.244.2.8
CNI1 --> VX1 : 路由: 10.244.2.0/24 via VXLAN IF
VX1 --> Underlay : 封裝成UDP 封包
Src=Node1_IP
Dst=Node2_IP
Underlay --> VX2 : 傳送到 Node2
VX2 --> CNI2 : 解封裝成 Pod 間封包
CNI2 --> PodB : 投遞給 Pod B

@enduml
{{< /plantuml >}}

---

## 6. 為什麼「PodCIDR 常常無法在實體網路被路由」？

技術上：

- `10.244.0.0/16` 是合法的 RFC1918 內網段，路由器當然 **可以** route。
- 問題不是「不能」，而是「**沒人會幫你 route**」。

### 6.1 實務上的三大問題

1. **企業網路不會為 Kubernetes 改 route**
   - 不會幫你加：  
     `10.244.1.0/24 -> Node1`、`10.244.2.0/24 -> Node2`、…
   - 不會接受你每天改動 PodCIDR 或 Node 數量。
2. **PodCIDR 容易與既有 10.x/172.x 網段衝突**
   - 企業內部可能已廣泛使用 `10.0.0.0/8` 的各種切割。
   - 你的 `10.244.0.0/16` 可能早被別的系統拿走。
3. **不允許你在核心網路上跑 BGP 給 Kubernetes**
   - 嚴謹的企業不會讓隨便一個新平台在 Backbone 上廣播 route。
   - Calico BGP 模式理論上可行，但在很多現場是政治問題。

因此：

> PodCIDR **理論上** 可被路由，但 **現實世界中往往不會被路由** → 就需要 Overlay（VXLAN）。

---

## 7. 為什麼雲端（AWS / GCP / Azure）多半不需要 VXLAN？

### 7.1 關鍵一句話

> **雲端 CNI 讓 Pod IP 直接變成 VPC/VNet 裡的「原生可路由 IP」，由雲端 SDN 負責 routing，不需要在 Node 間再搭 VXLAN overlay。**

### 7.2 AWS VPC CNI

- 每個 Pod 都拿到 **真實 VPC IP**。
- Pod IP = VPC 內的一個 Secondary IP / ENI 位址。
- VPC Router / Hypervisor 直接知道那些 IP 在哪個 Node。
- Pod 間通訊：
  - PodIP → VPC Fabric → PodIP
- CNI 不需要自己封裝 VXLAN。

### 7.3 GCP 原生 CNI / Dataplane v2

- Pod IP 直接掛在 GCP SDN（Andromeda）之下。
- GCP 自己的虛擬網路系統負責 L3 forwarding。
- 對使用者來說：Pod 間通訊 = 原生路由，不用 overlay。

### 7.4 Azure CNI

- Pod IP 直接分配在 VNet 的子網（Subnet）裡。
- Azure SDN 管理 PodIP ↔ Node 的對應關係。
- Pod-to-Pod / Pod-to-service 完全使用 VNet 路由。

### 7.5 雲端 vs On-Prem 網路架構差異圖

#### 7.5.1 On-Prem（需要 VXLAN 的典型情境）

{{< plantuml >}}
@startuml
title On-Prem：使用 VXLAN 的典型情境

node "Node1" {
  rectangle "Pod A 10.244.1.5" as PodA
  rectangle "VXLAN IF flannel.1" as VX1
}

cloud "企業實體網路 (不認識 10.244.0.0/16)" as CorpNet

node "Node2" {
  rectangle "VXLAN IF flannel.1" as VX2
  rectangle "Pod B 10.244.2.8" as PodB
}

PodA --> VX1 : Dst=10.244.2.8
VX1 --> CorpNet : L3 封裝
Src=Node1_IP
Dst=Node2_IP
CorpNet --> VX2
VX2 --> PodB

@enduml
{{< /plantuml >}}

#### 7.5.2 雲端（原生 SDN，不需要 VXLAN）

{{< plantuml >}}
@startuml
title 雲端：Pod 直接使用 VPC/VNet 可路由 IP

cloud "Cloud SDN / VPC Router" as SDN

node "Node1" {
  rectangle "Pod A 10.0.1.25" as PodA
}

node "Node2" {
  rectangle "Pod B 10.0.2.30" as PodB
}

PodA --> SDN : 送往 10.0.2.30
SDN --> PodB : 原生 L3 路由 (無封裝、無 VXLAN)

@enduml
{{< /plantuml >}}

> ✅ 關鍵差異：在雲端，**Pod IP 就是 SDN 的一等公民**，不需要額外用 VXLAN 再疊一層網路。

---

## 8. 面試 / 複習用超濃縮總結

可以直接背下面這段：

> **Kubernetes 裡，每個 Pod 由 CNI 分配一個可路由的 Pod IP，Pod 之間可以直接透過這些 IP 通訊。不過實務上我們多半透過 Service 的 ClusterIP，讓 kube-proxy 透過 iptables/IPVS 做 L4 負載平衡並轉到後端 Pod IP。**
>
> **跨 Node 的 Pod 通訊，需要確保 PodCIDR 在整個集群內可被路由。若實體網路願意幫你路由 Pod 網段，可以只用 L3 routing（例如 Calico BGP、Flannel host-gw），不需要 VXLAN。若實體網路不願意或無法為 PodCIDR 改 route，就必須透過 Overlay（最常見是 VXLAN）在 Node 間建立虛擬 L2 網路，實體網路只看到 NodeIP ↔ NodeIP 的 UDP 封包。**
>
> **在公有雲中，像 AWS VPC CNI、GCP、Azure CNI 會讓 Pod 直接使用 VPC/VNet 裡的原生可路由 IP，由雲端 SDN 負責 routing，因此多半不需要 VXLAN overlay。**

---

