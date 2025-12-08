---
date: '2025-11-26T00:00:00+08:00'
draft: true
categories:
  - system design
title: Messaging System（WhatsApp / Messenger 類）
---

# Messenger / WhatsApp --- **Format 3C 完整版**

## （Hybrid：口語講稿 + Technical Deep Dive + Multi-Region Messaging System）

------------------------------------------------------------------------

# 🎤 0. Opening（面試開場 45--60 秒）

今天我會用三層結構來解 Messenger / WhatsApp 的系統設計：

1.  即時訊息 baseline 架構：message delivery、ack、store‑and‑forward\
2.  Scalability
    深度解析：fan‑out、ordering、presence、backpressure、multi‑device
    sync\
3.  Multi‑region + end‑to‑end encryption（E2EE）+ offline durability

傳訊系統的挑戰不是「傳一則訊息」而已，而是如何在全球做到：

-   低延遲\
-   高可靠\
-   可恢復\
-   保證序（ordering）\
-   支援離線與多裝置\
-   高伸縮性（hundreds of millions concurrent users）

------------------------------------------------------------------------

# 1. 問題定義與 Use Cases

使用者希望：

-   即時收發訊息：P99 \< 100--200ms\
-   可離線：重新上線後需要拿到所有未讀\
-   多裝置同步（手機、桌面、Web）\
-   群組訊息：1 → 100 或更多\
-   已讀/送達回條（double check、blue ticks）\
-   Typing indicator\
-   End‑to‑End Encryption（伺服器看不到明文）\
-   Media upload（圖片、影片、語音）

------------------------------------------------------------------------

# 2. 功能性需求（Functional Requirements）

## 核心需求

1.  Send message\
2.  Deliver message\
3.  Ordering（per chat ordering）\
4.  Store‑and‑forward（offline queue）\
5.  Multi‑device sync\
6.  E2EE（Signal Protocol 類型）\
7.  Media upload & content delivery\
8.  Presence（online/offline）

## 進階需求

9.  Typing indicator\
10. Read receipts\
11. Message search（restricted by E2EE）

------------------------------------------------------------------------

# 3. 非功能性需求 + Capacity & Performance 估算

## 3.1 Performance Target

  功能                  延遲
  --------------------- -------------------
  1:1 message deliver   P99 \< 100--200ms
  presence update       \< 5s
  multi-device sync     eventual OK

## 3.2 QPS 估算

假設：

-   200M DAU\
-   平均每人 40 則訊息/天

```
    8B messages/day ≈ 92k msg/sec
    峰值 ≈ 500k–1M msg/sec
```
群聊 fan‑out 讓流量乘上 5--10 倍：
peak fanout send ~= 5M–10M msg/sec logical fan-out

## 3.3 Storage Estimation

假設每則訊息 400 bytes（metadata + ciphertext）：

    8B * 400 bytes = 3.2 TB/day
    一年 ≈ 1 PB（不含媒體）

Media 透過 CDN + object storage（S3/HDFS-like）儲存。

------------------------------------------------------------------------

# 4. 高階架構（Single-Region Baseline）

### 核心元件：

1.  **Gateway / LB**：TLS termination、routing\
2.  **Connection Service（WebSocket/MQTT）**\
3.  **Message Router（chat partitioner）**\
4.  **Message Log（append‑only）**\
5.  **Ack Service**\
6.  **Offline Queue（store-and-forward）**\
7.  **Push Notification**\
8.  **Presence（pub/sub）**\
9.  **Media Service（upload via object storage）**

------------------------------------------------------------------------

# 5. Component Deep Dive

## 5.1 Connection Service（WebSocket / MQTT）

功能：

-   維持長連線\
-   heartbeats（存活偵測）\
-   flow control（避免 client 過載）\
-   傳遞 ephemeral events（typing、presence）

------------------------------------------------------------------------

## 5.2 Message Router（per chat partition）

採：

    partition(chat_id) = hash(chat_id) % N

Router 行為：

1.  接收 sender 訊息\
2.  append 到 chat log\
3.  fan‑out to online receivers\
4.  更新 ack offset\
5.  寫入 offline queue（若 receiver 不在線）

------------------------------------------------------------------------

## 5.3 Message Store（append‑only log）

比 Kafka 更簡化的 per‑chat log：

-   immutable\
-   offset-based fetch\
-   高寫入性能（append only）\
-   分區（sharding by chat_id）

Client sync：

    client: give me messages since offset X

------------------------------------------------------------------------

## 5.4 Ack Service（3-level ack）
1.  server_received\
2.  delivered\
3.  read

UI 顯示：

-   ✓ sent\
-   ✓✓ delivered\
-   ✓✓ (blue) read

------------------------------------------------------------------------

## 5.5 Presence Service（online/offline）

-   不需強一致\
-   使用 TTL-based ephemeral entry（Redis / in-memory distributed
    store）\
-   pub/sub 推播好友狀態

------------------------------------------------------------------------

## 5.6 Multi-device Sync

Per device state：

    last_read_offset
    last_delivered_offset
    device_session_key

------------------------------------------------------------------------

# 6. 核心流程（Workflows）

## 6.1 Send message

1.  Sender → Connection Service\
2.  → Message Router（chat partition）\
3.  → append log\
4.  → push online receivers\
5.  → send ack to sender\
6.  → offline queue for offline devices

------------------------------------------------------------------------

## 6.2 Receive message（online）

1.  Router → connection → receiver\
2.  Receiver → ack delivered\
3.  Receiver UI → ack read

------------------------------------------------------------------------

## 6.3 Receive message（offline）

1.  Router 將訊息寫入 offline queue\
2.  Push service 通知\
3.  裝置上線後：

```
    client: give me messages since offset X
```
------------------------------------------------------------------------

## 6.4 Group messaging（fan-out）

採 **logical fan-out**：

-   訊息只寫一次（append log）\
-   Delivery service 對多個 device parallel deliver

------------------------------------------------------------------------

# 7. End-to-End Encryption（E2EE）

WhatsApp 採 **Signal Protocol**：

-   X3DH + Double Ratchet\
-   Per‑device session key\
-   Per‑message ephemeral key\
-   Server **無法解密** payload\
-   Server 僅負責 delivery / ordering / durability
Server 僅看得到：

-   sender_id\
-   receiver_id\
-   timestamp\
-   chat_id

不能做全文搜尋。

------------------------------------------------------------------------

# 8. Multi-region Architecture（Advanced）

## 8.1 Multi-region challenges

-   ordering\
-   latency（跨洲 RTT \> 150ms）\
-   replication\
-   failover\
-   presence fragmentation

------------------------------------------------------------------------

## 8.2 Region sharding patterns

### Pattern A：**Chat-based partition per region**（最佳）

-   每個 chat 分配一個 primary region\
-   所有訊息寫入該 region\
-   receiver 若在其他 region → latency 稍高但 acceptable\
-   ordering 簡單、可控

WhatsApp / FB Messenger 類似採用。

------------------------------------------------------------------------

### Pattern B：**Geo-local writers + Global ordering**（昂貴）

-   每個 sender 寫入最近 region\
-   使用 Lamport clock / Vector clock 做 ordering\
-   成本高、複雜度倍增\
-   面試中不建議採用

------------------------------------------------------------------------

## 8.3 Replication

Message log：

-   append-only\
-   async replicate to secondary region\
-   receiver offline → 可向任何 replica fetch history

------------------------------------------------------------------------

## 8.4 Failover

-   Global LB\
-   region health detection\
-   reassign chat partitions to healthy region

------------------------------------------------------------------------

# 9. Failure Handling

### Router crash

-   partitions reassigned\
-   replay from last committed offset

### Connection server down

-   client reconnect\
-   session resync

### Region outage

-   chat partitions migrate\
-   offline messages preserved via replicated log

------------------------------------------------------------------------

# 10. Follow-up Questions + Answers

------------------------------------------------------------------------
## Q1. 如何保證 per-chat ordering？

**A：**

-   one partition per chat\
-   append‑only log\
-   offset-based fetch\
-   avoid global ordering（昂貴）

------------------------------------------------------------------------

## Q2. 如何處理 group fan-out？

**A：**

-   logical fan-out（寫一次 log）\
-   parallel push to online devices\
-   offline devices 從 log pull

------------------------------------------------------------------------

## Q3. 如何處理 offline users？

**A：**

-   offline queue\
-   push notification\
-   device reconnect → get messages since offset

------------------------------------------------------------------------

## Q4. Typing indicator 如何實作？

**A：**

-   ephemeral event（不落地）\
-   pub/sub\
-   TTL ≈ 5 秒

------------------------------------------------------------------------

## Q5. 如何支援 multi-device E2EE？

**A：**

-   每裝置一組 session key\
-   server 不解密\
-   server 僅負責分發 encrypted payload

------------------------------------------------------------------------

## Q6. 如何縮短跨區延遲？

**A：**

-   chat partition 放在 active users region\
-   region affinity\
-   sticky routing

------------------------------------------------------------------------

# 11. PlantUML

{{< plantuml >}} 
@startuml 
actor Sender actor Receiver
Sender --> "Connection Service" : send() 
"Connection Service" --> "Message Router" : route(chat_id) 
"Message Router" --> "Message Log" : append() 
"Message Router" --> "Delivery Service" : push() 
"Delivery Service" --> Receiver : deliver()
Receiver --> "Ack Service" : delivered/read 
"Ack Service" --> "Message Router" : update()
"Message Router" --> "Notification Service" : push offline

@enduml 
{{< /plantuml >}}

## 5. Messaging System（WhatsApp / Messenger 類）

### 5.1 題目重述與假設

- 題目：設計一個即時訊息系統（1:1 / group chat）。  
- 功能需求：  
  - 發送文字訊息（後續可增圖片 / 檔案）  
  - 已讀 / 送達狀態  
  - 離線訊息、重新上線可收回歷史  
- 非功能需求：  
  - 低延遲（< 100ms）  
  - 高可用性、訊息不丟失  
  - 全球多 region 部署  

### 5.2 高階架構說明

- Client 與 Gateway 透過 WebSocket 或長連線維持通道。  
- Gateway 將訊息寫入 Message Queue（例如 Kafka）、再由 Chat Service 處理路由與存儲。  
- Message Store：可依 chat_id 分 shard，存訊息有序列表。  
- Push 路徑：接收訊息 → 寫入存儲 → 推送線上接收者；若離線，存離線隊列。  

### 5.3 PlantUML

{{< plantuml >}}
@startuml
title Messaging System - High Level Architecture

actor UserA
actor UserB

rectangle "Mobile / Web Client" as CLIENTA
rectangle "Mobile / Web Client " as CLIENTB

rectangle "Gateway (WebSocket / Long-lived)" as GW
queue "Message Queue (Kafka)" as MQ
rectangle "Chat Service" as CHAT
database "Message Store (sharded by chat_id)" as MSGDB
rectangle "Presence Service" as PRES

UserA --> CLIENTA : send message
CLIENTA --> GW : WS frame(msg)
GW --> MQ : enqueue message

MQ --> CHAT : consume msg
CHAT --> MSGDB : append to chat history
CHAT --> PRES : check recipient online?
PRES --> CHAT : online/offline

CHAT --> GW : push to online recipient
GW --> CLIENTB : deliver message

' Offline
CHAT --> MSGDB : mark undelivered
CLIENTB --> GW : reconnect
GW --> CHAT : sync request
CHAT --> MSGDB : load undelivered msgs
MSGDB --> CHAT
CHAT --> GW
GW --> CLIENTB : deliver offline messages

@enduml
{{< /plantuml >}}

### 5.4 口頭講稿（約 2–3 分鐘）

> 即時訊息系統的關鍵是「可靠投遞」與「低延遲」。  
> <br>
> 我會讓 Client 與 Gateway 維持 WebSocket 長連線，所有訊息透過 Gateway 進入後端。Gateway 把訊息寫入 Message Queue，再由 Chat Service 消費、存入 Message Store。這樣可以 decouple 短連線壓力，並利用 MQ 保證至少一次傳遞。  
> <br>
> Chat Service 寫入成功後，會查 Presence Service 判斷收件者是否在線，如果在線，透過 Gateway 的連線 channel 推送。如果不在線，就只寫入 Message Store 並標記為未送達，等對方重連時再拉取未讀訊息。  
> <br>
> 消息排序可依照 per-chat 的 sequence id，透過 sharding chat_id 保持順序。整體可以在 multi-region 部署，透過 region stickiness 確保單個會話不跨 region，降低複雜度。  

---