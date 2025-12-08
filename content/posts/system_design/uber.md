---
date: '2025-11-29T00:00:00+08:00'
draft: true
categories:
  - system design
title: Ride Hailing（Uber / Lyft 類）
---
# Uber / Ride-hailing System Design — Format 3C（Part 1）
## Opening + Requirements（Hugo-safe, no backticks）

---

## 🎤 Opening（60–90 秒）

我會把 Uber 的系統設計拆成三層：

1. **Baseline（單城市）**：Driver 位置更新、Rider 下單、派單（Dispatch）、Trip lifecycle。
2. **Scaling & Geo-indexing**：Driver location indexing、matching engine、city sharding、event streaming。
3. **進階議題**：ETA/Routing、Surge、Multi-region failover。

Uber 不是普通 CRUD，而是 **real-time geospatial matching** 的系統，所以架構的重心在：
- 高頻率動態資料（driver GPS updates）
- geospatial 資料結構  
- matching latency  
- 分散式 event pipeline  
- consistency model（trip strong consistency vs location eventual consistency）

---

# 1. Problem Definition（問題定義）

Uber 是一個 **即時雙邊市場（real-time two-sided marketplace）**。

Supply = Drivers  
Demand = Riders  

系統要在「數秒內」找出最佳 driver，核心問題包含：

- 如何找到附近 driver（geo search）  
- 如何排序（ETA-based ranking）  
- 如何處理 driver 狀態頻繁變化  
- 如何在全球、上百萬 conncurrency 下維持低延遲  

---

# 2. Functional Requirements（功能性需求）

## 2.1 核心功能

- Rider 發出 ride request  
- Driver 上傳 GPS 位置  
- Dispatch Service 找出最適合的 driver  
- Trip lifecycle：  
  ```
  REQUESTED → DRIVER_ASSIGNED → ARRIVING → IN_PROGRESS → COMPLETED
  ```
- Payment & fare calculation  
- Trip history  

## 2.2 進階功能（面試有餘裕可加分）

- Surge pricing（供需不平衡動態調整價格）  
- ETA（基於路網與交通模型）  
- Uber Pool（multi-rider routing）  
- Fraud detection（GPS spoofing）  

---

# 3. Non-functional Requirements（NFR）

## 3.1 Latency

| Operation | Target |
|----------|--------|
| Driver location update | P99 < 200–300 ms |
| Rider request → driver assigned | 1–2 sec |
| ETA / routing | < 200–300 ms |
| Trip state sync | < 500 ms |

## 3.2 Scalability Estimates

假設：

- 峰值 1M drivers  
- 每 3 秒送一次位置  

計算：

```
1,000,000 / 3 ≈ 333,333 driver location updates/sec
```

Ride requests：

```
3,000 – 8,000 RPS（global peak）
```

## 3.3 Consistency

| Component | Consistency |
|-----------|-------------|
| Driver location | Eventual OK（100–500ms acceptable） |
| Dispatch decision | Must use a consistent snapshot |
| Trip state | Strong consistency |
| Payment | Strong + idempotent |

---

# 4. System Scope（面試時口語）

我會專注於：

- Driver Location Index  
- Dispatch / Matching  
- Trip Lifecycle  
- Scalability（city-level partitioning, geo-sharding）  

不會花太多時間在 ML（ETA / surge），只概述必要部分。

---

# 5. System Actors

- **Rider**：發 ride request、查看 ETA、等待 driver  
- **Driver**：上傳 GPS、接單  
- **Dispatch Engine**：做 matching  
- **Trip Service**：管理 trip lifecycle  
- **Pricing / Payment**  

---

# 6. High-level Architecture Summary

主要的後端 service 有：

- API Gateway  
- Rider Service  
- Driver Service  
- **Driver Location Service（核心）**  
- **Dispatch Service（核心）**  
- Trip Service  
- Pricing / Surge Service  
- Payment Service  
- Kafka / Event Streaming  

---

# 7. Hot Path vs Cold Path

- **Hot path（低延遲要求）**：
  - Rider request  
  - Matching  
  - Driver location update  
  - Trip state changes  

- **Cold path（可延遲）**：
  - ML model updates  
  - Fraud detection pipeline  
  - Analytics  

設計上 Hot Path 要 stateless + fast I/O  
Cold Path 用 event streaming（Kafka）處理。

---

# 8. High-level Flow（E2E）

Rider → Request Ride  
→ Dispatch Service  
→ Query Driver Location Index for nearby drivers  
→ ETA / ranking  
→ Pick best driver  
→ Send request to driver  
→ Driver accepts  
→ Trip starts  
→ Live position streaming  
→ Complete trip  
→ Payment settled  

---

# 9. 小結（Part 1 完成）

你現在已經建立：

- 清楚的問題定義  
- 功能需求 / 非功能需求  
- 高階服務拆分  
- 核心流程  

下一步：進入 **Part 2：Architecture + Component Deep Dive**  
（Driver Location Index / Dispatch Engine / Trip Service）
# Uber / Ride-hailing System Design — Part 2  
## Architecture + Component Deep Dive（Hugo-safe, no backticks）

---

# 1. High-level System Architecture

Uber 的後端可概略拆成 8 大核心服務：

1. **API Gateway**  
2. **Rider Service**  
3. **Driver Service**  
4. **Driver Location Service（核心之一）**  
5. **Dispatch / Matching Service（核心之一）**  
6. **Trip Service（Trip State Machine）**  
7. **Pricing / Surge Service**  
8. **Payment Service**

背後則由：

- **Kafka / PubSub（事件流）**
- **Redis（快取）**
- **Geo-index storage（例如 H3, geohash, quad-tree）**
- **SQL + NoSQL（Trip / Driver / Rider metadata）**

組成完整的資料流。

接下來我會深入三個 Uber 面試最重視的 component：

- **Driver Location Service**
- **Dispatch / Matching Service**
- **Trip Lifecycle Service**

---

# 2. Driver Location Service（核心）

這是 Uber 最重要、最吃延遲的一部分。

Driver 位置更新頻率通常是：

```
每 2–3 秒上傳一次 GPS  
Driver 活躍量：可達百萬級  
→ 300k+ location updates per second
```

這意味著架構必須滿足：

- **高寫入吞吐量**  
- **低延遲使資料可立即供 Dispatch 使用**  
- **可快速查詢「附近 driver」**（geo-nearest search）

---

## 2.1 位置更新流程（Location Update Pipeline）

Driver App → API Gateway → Driver Location Ingest Service → Kafka → Location Indexer → In-memory Geo Index

整體流程採用 event-driven 架構。

---

## 2.2 Geo Index 選擇

Uber 需要支援「查詢半徑內最近 driver」，常見資料結構包括：

| 方法 | 優點 | 缺點 |
|------|------|------|
| Geohash Grid | 易分區、易 sharding | 邊界問題需合併查詢 |
| H3（hexagon grid） | Uber 內部使用、自動鄰近格網 | 計算量較高 |
| R-Tree | 高精度空間查詢 | 更新量大時效能下降 |
| Quad-tree | 好切 city partition | driver very dynamic，更新頻繁 |

多數 Ride-hailing 系統會使用：

> **Geohash Grid（或 H3）＋ In-memory index（Redis / custom memory store）**

以取得毫秒級查詢效能。

---

## 2.3 Geo-sharded In-memory Index

因為 driver location 是 ultra-hot path，所以通常：

- 資料會存在 **in-memory 的分散式資料結構**  
- 依 geohash / H3 cell 做 partition  
- 每個 cell 維護 driver list（driver_id → 坐標）

資料實例：

```
H3_cell_882a123 → [driver_19, driver_281, driver_9921]
H3_cell_882a124 → [driver_28, driver_31,...]
```

查詢半徑（radius search）流程：

1. 將 rider 的位置轉換成 geohash / H3 cell  
2. 查周邊 K 個鄰近 cell  
3. 合併 candidate list  
4. 計算距離 / ETA  
5. Ranking → 將前 N 個回傳給 Dispatch Matching  

---

# 3. Dispatch / Matching Service（核心）

這是 Uber 的靈魂。

### 決定派單需要考慮：

- Driver 與 rider 的距離  
- 預估到達時間（ETA）  
- Driver 的評分 / cancel rate  
- 車種需求（UberX / Black 等）  
- Surge（供需比）  
- Driver 是否在送單途中（多單併派邏輯）

Matching Engine 架構大致如下：

```
Rider Request  
→ Fetch nearby drivers (Location Service)  
→ Compute ETA for each  
→ Ranking model  
→ Pick top-1 (or top-k)  
→ Send dispatch request to driver  
```

---

## 3.1 Matching Process 詳解

### Step 1 — Rider 發起 by Rider Service

包含：

- 起點（lat, lng）  
- 目的地（lat, lng）  
- 車型  
- 付款方式  

資料送至 Dispatch Service。

---

### Step 2 — 查詢附近可用 driver

Dispatch → Driver Location Service

查詢：

```
find_nearby_drivers(lat, lng, radius = 1km)
```

輸出：

```
[driver_392, driver_991, driver_2041,...]
```

---

### Step 3 — ETA 計算

可能根據：

- road graph（路網）  
- 實時交通資料  
- 歷史交通模型（ML）  
- turn penalty  
- traffic speed estimation  

結果示例：

```
driver_392 → ETA 4 min  
driver_991 → ETA 6 min  
driver_2041 → ETA 3 min  
```

---

### Step 4 — Ranking & Scoring

Ranking model 可以是簡單 weighted sum：

```
score = α * ETA + β * driver_rating + γ * surge_factor
```

也可以是 ML-based ranking（深度模型）。

---

### Step 5 — Send Dispatch Request

Dispatch → Driver App：

- 距離  
- ETA  
- 預估收入  

Driver 端會倒數計時：

```
例如：15 秒內需接單  
```

---

### Step 6 — Driver Accept / Reject

- Accept → 建立 Trip  
- Reject → 重派（re-dispatch）

如果 driver 超時未回覆 → 當作 reject。

---

### Step 7 — Consistency & Concurrency Handling

必須避免：

- 多 driver 同時被 assign 同一 rider  
- 多 rider 同時被 assign 同一 driver  
- Trip state race condition

常見技巧：

- 使用 trip_id / driver_id 上的 **Compare-and-Swap（CAS）**  
- Trip Service 內強一致 DB（如 SQL transaction）  

例如：

```
UPDATE trips SET driver = A  
WHERE trip_id = X AND driver IS NULL
```

---

# 4. Trip Service（Trip Lifecycle）

Trip 是一個狀態機：

```
REQUESTED  
→ DRIVER_ASSIGNED  
→ DRIVER_ARRIVING  
→ IN_PROGRESS  
→ DROPOFF  
→ COMPLETED  
→ PAYMENT_SETTLED
```

Trip Service 提供：

- Trip state transitions  
- Validation（避免非法狀態跳躍）  
- Websocket / push event  
- 接 payment service 計費

Trip 資料會寫入 SQL（如 Postgres / MySQL）或分散式 DB（CockroachDB）。

---

# 5. Component 間的關係圖（不會用 backticks）

以下為 Hugo / PlantUML 版本：

{{< plantuml >}}
@startuml
actor Rider
actor Driver

Rider --> "Rider Service" : request ride
"Rider Service" --> "Dispatch Service"

Driver --> "Driver Location Service" : GPS update

"Dispatch Service" --> "Driver Location Service" : find nearby drivers
"Dispatch Service" --> "ETA/Ranking Engine" : compute ETA + score

"Dispatch Service" --> Driver : dispatch request
Driver --> "Dispatch Service" : accept/reject

"Dispatch Service" --> "Trip Service" : create trip
"Trip Service" --> Rider : trip updates
"Trip Service" --> Driver : trip updates
@enduml
{{< /plantuml >}}

---

# ✔️ Part 2 完成（你可直接貼到 .md）

下一步如果你需要，我可以繼續提供：

- **Part 3：Matching Algorithms + ETA + Routing（完整版）**  
- **Part 4：Scaling、City-level sharding、Multi-region Architecture**  
- **Part 5：Follow-up Q&A + Deep technical reasoning**

只要回覆：

👉 **Next: Part 3**

# Uber / Ride-hailing System Design — Part 3  
## Matching Engine + ETA + Routing（Full Deep Dive, Hugo-safe formatting）

---

# 1. Matching Engine（派單引擎）核心概念

Dispatch / Matching Engine 是 Uber 的核心競爭力。  
它必須：

- 延遲非常低（< 1–2 秒）  
- 高吞吐（城市峰值 ~5k–20k RPS）  
- 在地理空間上找出合理的 driver  
- 正確處理 heavy concurrency（大量 driver 同時更新位置）  
- 做到「人性化 + 高接受率」的派單策略  

Matching Engine 的任務是：

```
Input: rider location, destination, rider profile  
Output: best driver (or ranked top-K)
```

它依賴三大資料來源：

1. **Nearby driver candidates**（Location Service）
2. **ETA**（Routing/Mapping Service）
3. **Scoring Model**（rule-based or ML-based）

---

# 2. Matching Pipeline（派單流程完整拆解）

完整的 matching pipeline：

```
Rider Request
→ Get Nearby Drivers
→ Filter
→ Compute ETA
→ Ranking & Scoring
→ Dispatch to top driver
→ Driver Accept/Reject
→ (If reject: re-dispatch)
```

我們逐步解析。

---

# 3. Step 1：Find Nearby Drivers（找附近司機）

Matching 首先呼叫 Driver Location Service：

```
drivers = location_service.find_nearby(lat, lng, radius=1-3km)
```

可能的 driver 數量：

- 人口密集城市：有時一次可找到 **100–600 drivers**  
- 郊區：可能只有 5–20 drivers  

但不能全部拿去算 ETA（太慢），所以第一步是：

## 3.1 Candidate Filtering（候選司機過濾）

篩選：

- 線上（Online）  
- 空車（Available）  
- 車型符合（UberX / Black / Comfort）  
- 評分 / 安全條件  
- 最近取消率過高 → 降低優先順序  
- 已接太多單、休息模式 → 排除  

---

# 4. Step 2：ETA Engine（路線預估引擎）

Uber 的 ETA 是一個獨立服務，依靠：

- **路網（road graph）**
- **實時交通（traffic model）**
- **歷史交通 pattern**
- **特殊事件（道路封閉、事故）**

它回傳：

```
ETA(driver_location → rider_pickup_location)
ETA(rider_pickup → rider_dropoff)
Route shape
Distance
```

延遲需求：

- **P99 < 200–300 ms**
- 因為匹配必須在 1–2 秒內完成

---

# 5. Step 3：Driver Scoring（司機排名模型）

Uber 的 ranking 會考量：

| 因素 | 描述 |
|------|-------|
| ETA | 越短越好 |
| Driver rating | 分數越高越優先 |
| Acceptance rate | 接單率高 → 派單成功率高 |
| Cancellations | 不想派給愛取消的司機 |
| Surge incentive | 較高收入區可以提高 driver 意願 |
| Driver fatigue | 長時間上線 → 降權或提示休息 |

可以用 rule-based：

```
score = α*(ETA) + β*(driver_rating) + γ*(surge) + δ*(accept_rate)
```

或 ML model（大公司更常用）。

Ranking output：

```
ordered_drivers = sort_by(score)
best_driver = ordered_drivers[0]
```

---

# 6. Step 4：派單（Dispatch Request）

Dispatch Service → Driver App：

內容包含：

- 預估收入  
- ETA  
- Rider 評分  
- 距離  
- 派單倒數計時（通常 8–15 秒）

---

# 7. Step 5：Driver Accept / Reject

如果 driver **接受**：

- 建立 Trip（Trip Service）  
- Trip 狀態變為 DRIVER_ASSIGNED  

如果 driver **拒絕 / 超時未回覆**：

兩種策略：

### A) Re-dispatch（重新派給下一位候選 driver）
- 避免重新計算所有 drivers  
- 使用 ranking 選出下一位  

### B) Recompute Nearby + ETA（完全重算）
- 若延遲太久，附近司機位置可能已大幅變動  

實際 Uber 會依照區域需求選擇 A 或 B。

---

# 8. Step 6：Handling Concurrency（避免競態）

常見競態：

1. 多個 driver 同時搶同一個 trip  
2. 同一個 driver 同時接到不同 trip  
3. 兩個 dispatch worker 同時派單  

解法：

### 8.1 Optimistic Lock（樂觀鎖）

Trip assignment：

```
UPDATE trips SET driver_id = <candidate>
WHERE trip_id = X AND driver_id IS NULL
```

若返回 0 rows → 表示 trip 已被其他 driver 接走。

### 8.2 CAS（Compare & Swap）方式

在 Redis/Etcd 做 driver state check：

```
driver_state == AVAILABLE → ASSIGNING
ASSIGNING → ASSIGNED
```

### 8.3 Idempotent Operations

派單、trip transitions 都應可安全重試。

---

# 9. Routing Engine（路徑引擎）

Routing 是 ETA 的核心，但也能獨立運作，用於：

- 計算費用（distance-based）  
- 計算 driver detour（共乘時很重要）  
- 預估到達時間  

資料來源：

- OSM  
- Google Maps-like service  
- Uber 內部自建地圖（高度優化）  

Routing pipeline：

```
origin → nearest road node  
destination → nearest road node  
→ run modified Dijkstra / A*  
→ apply traffic weighting  
→ return route + travel time
```

---

# 10. Surge Pricing（即時動態定價）

這屬於進階議題，可以做為加分：

Surge = Supply / Demand ratio

例：

```
if demand >> supply → surge_multiplier ↑
if supply >> demand → multiplier = 1
```

Surge 影響：

- rider price  
- driver incentive  
- ranking model 也會用到這個參數  

---

# 11. End-to-End Matching Sequence（PlantUML）

以下為 Hugo 用法：

{{< plantuml >}}
@startuml
actor Rider
actor Driver

Rider --> "Dispatch Service" : request ride

"Dispatch Service" --> "Driver Location Service" : nearby drivers
"Driver Location Service" --> "Dispatch Service" : candidates

"Dispatch Service" --> "ETA Engine" : compute ETA
"ETA Engine" --> "Dispatch Service" : ETA list

"Dispatch Service" --> "Scoring Engine" : rank drivers
"Scoring Engine" --> "Dispatch Service" : best driver

"Dispatch Service" --> Driver : dispatch request
Driver --> "Dispatch Service" : accept/reject

"Dispatch Service" --> "Trip Service" : create trip
@enduml
{{< /plantuml >}}

---

# ✔️ Part 3 完成（可直接存成 .md）

下一步如果你願意：

👉 **Next: Part 4（Scalability + Multi-region + Fault Tolerance）**

我會用同樣的 Hugo-safe Markdown 格式繼續輸出！
# Uber / Ride-hailing System Design — Part 4  
## Scalability, Multi-region Architecture, City Sharding, Fault Tolerance  
### (Hugo-safe, production-quality, 35–45 min SD interview depth)

---

# 1. Scalability Challenges（Uber 為什麼難？）

Uber 的負載不是一般 Web CRUD：

1. **Driver 位置高度動態（每 2–3 秒上報 GPS）**  
2. **地理空間查詢密集（geo-nearest、ETA、routing）**  
3. **大量併發（millions of active drivers & riders）**  
4. **城市之間彼此獨立負載，資料不能混用**  
5. **某一城市尖峰需求極高（新年、跨年、場館活動）**

因此系統必須支援：

- 依「城市 city」進行分片  
- 多資料中心（multi-region）  
- 熱區（hotspot）防禦  
- 事件驅動架構（Kafka）  
- 水平擴展（horizontal scaling）

---

# 2. City-level Sharding（依城市分片）

Uber 的最大 scalability insight：

> **一個城市的 demand 和 supply 彼此獨立，可以是獨立的 cluster。**

例如：

- New York（NYC）  
- San Francisco（SF）  
- Tokyo  
- Taipei  

每個城市可以有自己的一組服務：

```
location-service-nyc  
location-service-sf  
location-service-tokyo  
dispatch-service-taipei  
```

### 優點：

- 單城市的 load 不會壓垮全球系統  
- dispatch 只需查詢本城 driver（大幅降低 search scope）  
- 故障隔離  
- 可以根據城市負載獨立擴展（NYC >> Omaha）

### 挑戰：

- traveler roaming（旅客跨城使用）  
- 多城市紀錄需要 global storage（history & billing）  
- global payment settlement 需跨 shard

---

# 3. Driver Location Scaling（高頻位置更新的水平擴展）

Driver Location 是最吃資源的部份：

```
> 300k - 1M location updates/sec (global peak)
```

### 3.1 水平切分方式

1. **按 geo cell（H3 / Geohash）分片**  
2. **按城市分片**（最常用）  
3. **Hybrid：城市內再用 geohash 分段**

### 3.2 In-memory 分散式 geo index

通常使用：

- Redis Cluster（geo index）  
- 自研 In-memory HashMap  
- Aerospike（低延遲 + geospatial）  
- Uber 自己的 M3 機制（類似 memcache cluster）

資料格式：

```
city → geocell → [driver_ids...]
```

查詢時只掃描鄰近 cell，而非整個城市。

---

# 4. Dispatch Service Scaling

Dispatch 是 compute-heavy：

- 要排名大量 candidates  
- 要計算 ETA（可能調用 routing engine）  
- 要處理 driver 接單/拒單  
- 要處理併發（避免一單多派）

因此 Dispatch Service 通常設計為：

### 4.1 Stateless services（可水平擴展）

- 使用 Load Balancer 分配請求  
- worker 數量可以在高峰時水平增加  
- state（trip states, driver status）放在 DB / Redis / etcd  

### 4.2 使用 Fast caches

- 缓存 nearby drivers（短期 TTL）  
- 缓存 ETA 結果（目的地相似可重用）

---

# 5. Routing Engine Scaling（路網與交通）

Routing computation 非常昂貴：

- 圖演算法（A*, Dijkstra variants）  
- 動態交通權重  
- 複數備援服務需要同步

Scaling 策略：

1. **Precomputed routing graph（分段緩存）**  
2. **分城市 cluster caching**  
3. **近似算法（bidirectional A*）**  
4. **模糊 ETA（允許 ±10% 誤差） → 快速回應**

Uber 實際會建：

- **Routing Service Pool** per city  
- **Traffic model service（ML）**

---

# 6. Kafka-based Event Streaming（全系統的 backbone）

Uber 的後端大量使用 **event streaming**，因為：

- Trip events（trip_created, trip_updated）  
- Driver location updates  
- Payment events  
- Fraud signals  
- ML feature pipelines  

典型架構：

```
Driver → Location Ingest → Kafka (topic: driver-locations)
Trip Service → Kafka (topic: trip-events)
Payment Service → Kafka (topic: transactions)
```

消費者包括：

- analytics  
- fraud system  
- ML pipelines  
- dashboard  
- replay system（event sourcing）

---

# 7. Multi-region Architecture（多資料中心）

雖然城市是 shard，但全球架構仍需：

- 多 Region（US-East、US-West、EU、APAC）  
- 每個 region 含多個城市 clusters  
- Payment / history / identity 為 global services  
- Data replication

Uber 類的 multi-region 設計要解決：

### 7.1 Driver / Rider 跨區使用（Roaming）

例如：台灣人飛東京，在東京叫車  
→ 使用東京城市 cluster，但 rider account 是 global service。

因此需要：

- **Global Identity Service（User / Driver Profile）**  
- **Local City Dispatch Cluster**  
- **Shared Payment Service**  
- **History Service（global DB 或 multi-region DB）**

---

# 8. Fault Tolerance（容錯設計）

必考內容，以下整理最重要的實作手法。

---

## 8.1 Driver Location Service 故障

若 location index 失效：

- fallback to read last-known location  
- degrade search radius（降低精度但服務不中斷）  
- multi-replica in-memory stores  
- 若整個城市 index crash → 切換到 backup cluster

---

## 8.2 Dispatch Service 故障

Dispatch workers stateless → 可快速水平恢復。

若 dispatch cluster 宕機：

- 透過 queue（Kafka）重播 pending requests  
- 未完成的 matching 重新計算  
- 支援 idempotent trip creation

---

## 8.3 Trip Service 故障

策略：

- 強一致 DB（SQL + primary/replica）  
- 使用 Write-Ahead-Log（WAL）  
- 若 primary region down → promote replica  

Trip service 屬於「strong consistency」領域。

---

## 8.4 Payment Service（絕不可重扣或漏扣）

保護機制：

- idempotency keys  
- two-phase commit（視需求）  
- retry-safe API  
- exactly-once guarantees（邏輯層）  

---

## 8.5 City Cluster Outage（整個城市故障）

若 NYC cluster 全掛：

1. rider 無法叫車（NYC city shard 失效）  
2. rider 帳號仍在 global  
3. 其他城市不受影響  
4. 系統呈現「區域性故障，不影響全球」

這種設計保證：

- **城市故障 → 不會形成全球性事故**

---

# 9. Multi-region Failover & Traffic Routing

流量路由一般交由：

- Global Load Balancer  
- GeoDNS  
- Anycast（視公司規模）

但 **dispatch 永遠落在城市 cluster**：

```
global services (identity/payment/history)
local services (dispatch/location/trip)
```

不能跨城 dispatch（LA 不能指派 SF 的 driver）。

---

# 10. Architecture Diagram（Hugo-safe PlantUML）

{{< plantuml >}}
@startuml
actor Rider
actor Driver

cloud "Region Cluster" {
    node "City Cluster (e.g., NYC)" {
        [API Gateway]
        [Rider Service]
        [Driver Service]
        [Driver Location Service]
        [Dispatch Service]
        [Trip Service]
        [Pricing Service]
    }

    [Driver Location Index] --> [Dispatch Service]
    [Dispatch Service] --> [Trip Service]
    [Trip Service] --> [Pricing Service]
}

cloud "Global Services" {
    [Identity Service]
    [Payment Service]
    [History Service]
}

Rider --> [API Gateway]
Driver --> [API Gateway]

[Trip Service] --> [Global Services]
@enduml
{{< /plantuml >}}

---

# ✔️ Part 4 完成！  
你可以直接複製存成：`uber_part4_scaling_multiregion.md`

下一步：  
👉 **Next: Part 5（Follow-up Q&A + Deep System Design Reasoning）**

會包含：

- 20–30 題 follow-up  
- 每題都有帶深度、有技術含量的標準回答  
- 讓你面試時可反問 / 深談 / 展示思考深度

只要回覆：**Next: Part 5**！
# Uber / Ride-hailing System Design — Part 5  
## Follow-up Questions + Deep Reasoning Answers  
### (Hugo-safe, production-quality, for 45–60 min system design interviews)

---

# 1. Follow-up：How do you scale Driver Location Service to 1M+ drivers?

### Key Points：
- 位置更新量可能突破：

```
> 300,000 – 1,000,000 updates/sec
```

- 無法寫入 SQL（太慢）  
- 必須使用 in-memory geo index

### Ideal Answer：

1. **City-level sharding**  
   - 每個城市都有自己的 Driver Location cluster  
   - 城市之間互不干擾（隔離 fault domains）

2. **Geo-spatial partitioning（H3 / Geohash）**  
   - 根據 H3 Cell → 將 driver 數據分散到不同節點  
   - 每個節點只負責部分地理區域

3. **In-memory datastore（Redis Cluster / custom memory service）**  
   - 支援毫秒級 read/write  
   - 使用 sorted sets（距離排序）或 hash buckets

4. **Event pipeline（Kafka）**  
   - Location ingest → Kafka → Index updater  
   - 支援 replay / recovery

5. **Aggressive TTL（位置不應保存太久）**  
   - 3–10 秒內未更新 → 視為 offline/unavailable  

---

# 2. Follow-up：如何避免「邊界效應」（Geo cell boundary issue）？

### 問題：

Geohash / H3 cell 會造成：

- rider 與 driver 分別落在不同 cell  
- search radius 看似很近但跨了 cell boundary → driver 被漏掉

### 解法：

1. **查詢鄰近 cell（k-ring lookup）**  
   - H3 的 `k-ring` 可直接找出周圍 cells  
   - 避免漏查

2. **擴大查詢半徑**  
   - radius-based search 而非單 cell search

3. **動態 cell resolution**  
   - 車多時 → 提高解析度（更細 cell）  
   - 車少時 → 降低解析度（更大 cell）

---

# 3. Follow-up：What happens if two drivers accept the same trip?

這是典型 **race condition**。

### 正確解法：

使用 **Optimistic Locking（SQL CAS）**：

```
UPDATE trips 
SET driver_id = D1
WHERE trip_id = X AND driver_id IS NULL
```

若成功 → D1 接單成功  
若失敗 → trip 已被其他 driver 接走 → 回傳 reject 給 driver

這也是為什麼 Trip Service 必須保持 **strong consistency**。

---

# 4. Follow-up：Trip lifecycle 如何保持強一致？

Trip 狀態不能亂跳：

```
REQUESTED  
→ ASSIGNED  
→ ARRIVING  
→ IN_PROGRESS  
→ COMPLETED  
→ PAYMENT_SETTLED
```

必須避免：

- ASSIGNED → COMPLETED  
- IN_PROGRESS → REQUESTED  
- CANCELLED → COMPLETED  

### 解法：

- 使用 relational DB（Postgres / MySQL）  
- 以 **行級鎖 / transaction** 管控狀態  
- 每次更新：

```
UPDATE trips 
SET state = NEW_STATE 
WHERE trip_id = X AND state = OLD_STATE
```

此模式也稱 **Compare-and-Swap**。

---

# 5. Follow-up：如果 ETA Engine 延遲太高怎麼辦？

Routing & ETA 通常是最慢的 service。

### 緩解方案：

1. **Cache frequent routes**
   - 起點/終點 cluster-based caching  
   - 熱門 pickup/dropoff 組合可事先預計算  

2. **降低精度**
   - 由細緻 routing → 與 traffic model 合併簡化  
   - ETA 容許 ±10% 誤差，只要排序正確即可

3. **批量請求（batch ETA）**  
   - 一次拿多個候選 driver  
   - 由 ETA Engine 批次回傳結果  

4. **A/B 測試不同 routing 引擎**  

---

# 6. Follow-up：如何處理 Surge Pricing（動態調價）？

Surge = demand / supply ratio in local geo cell

### 計算方式：

1. 計算單 cell 當前：
   - 活躍 drivers  
   - 發出的 ride requests  

2. 若：

```
demand >> supply
```

則計算 Surge multiplier：

```
multiplier = f(demand/supply)
```

3. Surge 可影響：
   - rider 費用  
   - driver incentive（提高意願）  
   - matching ranking（優先考慮在 surge zone 的 driver）

---

# 7. Follow-up：如何設計 Uber Pool / Shared Rides？

這是一個 NP-hard routing problem：

- 多乘客  
- 多目的地  
- 動態加入（插單）  
- driver route must adjust in real time  

主要使用：

- **Insertion heuristic（插入式算法）**  
- **ETA penalty minimization**  
- 限制 search space（避免全局暴力計算）

---

# 8. Follow-up：如何做 Multi-region Disaster Recovery？

### Global service（identity, payment） → multi-region active-active  
### City cluster（dispatch, location） → active-standby

如果某 region down：

- 調度 / 叫車功能停用（只停該城市）  
- 支付 / 履歷仍能用（global）  
- 其他地區不受影響  

重點：  
**城市 = fault containment zone（故障隔離單元）**

---

# 9. Follow-up：跨城市行程如何處理？

例如：司機從 NYC 開到 New Jersey。

解法：

- 每筆 Trip 所屬城市不變（NYC cluster 仍維護該 trip）  
- driver location 可隨城市切換被 sync 到鄰近 cluster  
- 若 driver 進入全新城市 → trigger re-registration 到新 city cluster

---

# 10. Follow-up：如果 Driver Location Service 崩潰？

### 系統降級（Graceful Degradation）：

1. 使用 last-known location（延遲 5–10 秒）  
2. 減少 search precision  
3. fallback to broader geohash zones  
4. allow dispatch with reduced ETA accuracy  
5. 重新同步地理索引（rebuild index）  

---

# 11. Follow-up：你會如何減少 Dispatch tail latency（P99 呈現飆高）？

1. **限制 candidates 數量**  
   - e.g., only pick top 50 nearest drivers  

2. **Reduce ETA calls**  
   - 先粗略篩掉不可能的 driver  
   - 批量查詢 ETA

3. **Reduce RPC fan-out**  
   - 串接 service 過多 → latency 疊加  
   - 將 ranking and ETA 放在同 cluster

4. **使用 async pipeline**  
   - 接到 ride request 立即回覆「正在派單」  
   - 實際匹配在 async worker 進行

---

# 12. Follow-up：資料庫設計問題 — Trip Table 長太快怎麼辦？

Trip 數量巨大：

```
50M – 100M trips/day → 18B+ trips/year
```

方案：

1. **Time-based partitioning（SQL partition）**  
2. **Cold storage（S3 / HDFS）**  
3. **只保留 active trips 在 hot table**

---

# 13. Follow-up：如果城市突然爆量（演唱會散場）？

解決方式：

- auto-scaling dispatch workers  
- pre-increase Redis / Location store capacity  
- push driver incentives（surge）  
- event prediction（ML）  
- temporary relax ETA precision  
- increase cancel/decline penalties  

---

# 14. Follow-up：如何讓 matching 更公平？

加入：

- driver long-idle boosting  
- reduce driver starvation  
- weighted random choices among top-K  

---

# 15. Follow-up：driver 惡意離線重上線（為搶單）怎麼辦？

Check abnormal patterns：

- frequent online/offline toggles  
- location jumps（GPS spoofing）  
- matching acceptance rate  

可由 fraud engine 處理。

---

# 16. Follow-up：如何避免「多單搶占」（multi-rider conflict）？

對每個 driver 建立 **driver assignment lock**：

```
driver_state = AVAILABLE
driver_state = ASSIGNING (lock)
driver_state = ASSIGNED
```

使用 Redis / etcd 保證 atomicity。

---

# 17. Follow-up：如何降低 Matching Service 的成本？

- 使用模糊 ETA（節省 routing 計算）  
- 限制候選 driver 數量  
- 使用地理 partition  
- 對 driver acceptance 做預測  
- 用 cheaper hardware cache（in-memory grid）  

---

# 18. Follow-up：推播通知如何設計（driver / rider）？

使用：

- WebSocket（trip updates）  
- APNS / FCM（派單通知）  
- server-side event queues  

notification service 要 retry-safe。

---

# 19. Follow-up：在高併發下如何避免 payment double charge？

使用：

- idempotency keys  
- database uniqueness constraint  
- transaction logs（WAL）  
- async settle queue  

---

# 20. Full Follow-up: PlantUML Diagram

{{< plantuml >}}
@startuml
actor Rider
actor Driver

Rider --> (Ride Request)
(Ride Request) --> [Dispatch Service]

[Dispatch Service] --> [Driver Location Service] : find candidates
[Driver Location Service] --> [Dispatch Service] : nearby drivers

[Dispatch Service] --> [ETA Engine] : ETA batch request
[ETA Engine] --> [Dispatch Service]

[Dispatch Service] --> Driver : dispatch request
Driver --> [Dispatch Service] : accept/reject

[Dispatch Service] --> [Trip Service] : create/update trip

[Trip Service] --> [Payment Service] : settle payment

@enduml
{{< /plantuml >}}

---

# ✔️ Part 5 完成！

你可以直接存成：  
**`uber_part5_followups.md`**

---

如果你需要：

### ✔ 把五個 part 自動整併成一份完整的 `.md`
### ✔ 自動產生 `.docx`（排版良好可印面試講義）
### ✔ 產出題庫封面 / 一鍵生成 PDF
### ✔ 開始下一題（e.g., Instagram feed / TiDB / Web Crawler）

只要告訴我：  
👉 **“整併成一份”** 或 **下一題的主題**！





## 8. Ride Hailing（Uber / Lyft 類）

### 8.1 題目重述與假設

- 題目：設計類 Uber 系統。  
- 功能需求：  
  - 乘客發起叫車，匹配附近司機  
  - 計算預估到達時間（ETA）  
  - 行程建立、費用計算與付款  
- 非功能需求：  
  - 位置更新頻繁（幾秒一次）  
  - 大量即時讀寫（查附近司機）  
  - 需考慮多 region / city 的擴展性  

### 8.2 高階架構說明

- Driver / Rider App 持續上報 GPS 到 Location Service。  
- 匹配服務從 Location Store 中查詢附近可接單司機。  
- 狀態機：driver 狀態（available / matching / on-trip），trip 狀態（requested / accepted / on-going / finished）。  

### 8.3 PlantUML

{{< plantuml >}}
@startuml
title Ride Hailing - High Level Architecture

actor Rider
actor Driver

rectangle "Rider App" as RA
rectangle "Driver App" as DA

rectangle "API Gateway" as API
rectangle "Location Service" as LOC
cloud "Location Store (Geo-indexed)" as LOCSTORE

rectangle "Matching Service" as MATCH
rectangle "Trip Service" as TRIP
database "Trip DB" as TRIPDB

rectangle "Pricing Service" as PRICE
rectangle "Payment Service" as PAY

Driver --> DA : send GPS updates
DA --> API : /driver/location
API --> LOC : update location
LOC --> LOCSTORE : upsert driver location

Rider --> RA : request ride
RA --> API : POST /ride-request
API --> MATCH : find nearby drivers
MATCH --> LOCSTORE : query drivers near rider
LOCSTORE --> MATCH : candidate drivers
MATCH --> DA : push request
DA --> API : accept/decline
API --> MATCH
MATCH --> TRIP : create trip
TRIP --> TRIPDB : persist trip

TRIP --> PRICE : fare estimate
PRICE --> TRIP
TRIP --> PAY : charge on completion
PAY --> TRIP : payment result

@enduml
{{< /plantuml >}}

### 8.4 口頭講稿（約 2–3 分鐘）

> Ride Hailing 系統的核心是「位置服務 + 匹配引擎 + 行程狀態機」。  
> <br>
> 司機端 App 定期回報 GPS 給 Location Service，Location Service 會把司機的位置寫入一個支持 geo index 的儲存（例如 Redis GEO、專用 geo store）。乘客發起叫車時，Matching Service 根據乘客位置在 Location Store 中查詢附近的 available drivers。  
> <br>
> 匹配成功後會在 Trip Service 中創建一個 trip 記錄，並進入狀態機管理整個行程（requested、accepted、on-trip、completed 等）。價格可由 Pricing Service 根據路程、時間與 surge 等因素計算，行程結束後由 Payment Service 進行扣款。  
> <br>
> 整體系統可以按城市做分區部署，Location Service 與 Matching Service 一般會強依賴 local region 的資料，以降低延遲。  
---