---
date: '2025-11-21T00:00:00+08:00'
draft: true
categories:
  - system design
  - eventual consistency
title: URL Shortener（Bitly 類系統）
---
# URL Shortener --- **Format 3C**

## （Hybrid：口語講稿 + Technical Deep Dive + Multi-Region）

------------------------------------------------------------------------

## 🎤 0. Opening（面試開場 45--60 秒）

我會把 URL Shortener 的設計切成三個層次來說明：

1.  單 Region 的標準架構（single-region baseline）\
2.  scalability / performance / capacity 的技術深挖\
3.  全球 multi-region + edge caching 的進階設計

過程中我會先用一個簡化的 high-level 架構建立我們的共同理解，之後再逐步往
ID 產生、儲存、快取、analytics pipeline 以及 multi-region consistency
做深入說明。

------------------------------------------------------------------------

## 1. 問題定義與 Use Cases

URL Shortener 的核心目標是將長 URL 映射成短
URL，並在使用者點擊短網址時快速、可靠地重新導向到原始 URL。

典型 example：

    Long URL:  https://www.example.com/products/view?id=123456789
    Short URL: https://s.io/Ab3XyZ

此系統需支援大規模高讀取量、高 QPS
redirect、全球高可用、多區部署等需求。

------------------------------------------------------------------------

## 2. 功能性需求（Functional Requirements）

### Core

1.  Create Short URL（long → short mapping）\
2.  Redirect（短網址 302/301 導到長網址）\
3.  Optional:
    -   Custom Alias\
    -   Expiration\
    -   Analytics（click count, referrer, geo, UA）

### Enterprise

-   SSO / tenant-based policy\
-   Abuse detection\
-   Rate limiting

------------------------------------------------------------------------

## 3. 非功能性需求 + Capacity / Performance 估算

### Latency

-   Redirect P95 \< **50ms**
-   Create short URL P95 \< **200ms**

### Throughput

假設：

-   每天新增短碼：50M\
-   每天 redirect：5B

Redirect：

    5e9 / 86400 ≈ 57,870 QPS 平均  
    峰值 ≈ 200k–500k QPS

Create：

    50M / 86400 ≈ 580 QPS 平均  
    峰值 ≈ 5k–10k QPS

### Storage Capacity

假設 average entry ≈ 400 bytes：

    400 bytes * 1e9 entries = 400 GB

加上 index / replica → 1--2 TB 成本。

------------------------------------------------------------------------

## 4. 高階架構（Single-Region Baseline）

元件：

1.  API Gateway / LB\
2.  Stateless URL Service\
3.  ID Generator（Snowflake）\
4.  KV Store（DynamoDB / Cassandra）\
5.  Redis Cluster\
6.  Kafka + Stream Processor（Analytics）

------------------------------------------------------------------------

## 5. Component Deep Dive

### 5.1 ID Generator

Snowflake：

    [timestamp | region_id | worker_id | sequence]

優勢：

-   時間序、可排序\
-   無需共識\
-   分散式生成、避免碰撞\
-   Base62 編碼後 8--10 chars

------------------------------------------------------------------------

### 5.2 Storage Layer（NoSQL）

為什麼用 NoSQL：

-   單 key lookup\
-   高吞吐、低延遲\
-   自動分片

Key = short_code\
Value = long_url + metadata

------------------------------------------------------------------------

### 5.3 Redis Cache

Cache-aside：

    Redis hit → redirect  
    Redis miss → DB lookup → write cache

TTL：通常設定數小時～數天\
Hot keys 永續保持（pin）

------------------------------------------------------------------------

## 6. Redirect Flow（Single-Region）

    User → LB → URL Service → Redis (hit?)  
     → yes: redirect  
     → no: DB lookup → write Redis → redirect

Analytics：

-   非同步丟 Kafka\
-   不阻塞 redirect 路徑

------------------------------------------------------------------------

## 7. Multi-Region Global Deployment（進階）

### 7.1 Requirements

-   全球低延遲\
-   Async replication\
-   Eventual consistency 可接受\
-   Failover 必須快速、無痛

------------------------------------------------------------------------

### 7.2 Geo Routing

-   GeoDNS / Anycast\
-   將使用者導向最近 Region（US/EU/APAC）

------------------------------------------------------------------------

### 7.3 Multi-Region ID Generator

加入 `region_id` 避免 split-brain：

    [timestamp | region_id | worker_id | sequence]

每個 region 獨立生成，沒有碰撞風險。

------------------------------------------------------------------------

### 7.4 Replication

使用 DynamoDB Global Table 或 Cassandra multi-DC：

-   每次 create 都寫 local region\
-   AWS / Cassandra 自動 replicate 到其他 region\
-   延遲大約 100ms--2s

若在遠端 region 查不到短碼：

-   fallback 查主 region\
-   回寫 local region cache

------------------------------------------------------------------------

### 7.5 Edge Worker / Edge KV

Redirect latency 降到 5--20ms：

流程：

1.  User → 最近 Edge PoP\
2.  Edge Worker 查 local KV\
3.  Miss → origin region 查詢 → 回寫 edge

------------------------------------------------------------------------

## 8. Failure Handling（故障與降級）

### Redis down

-   fallback DB\
-   enable partial traffic shed\
-   avoid cache stampede（singleflight）

### Region Down

-   DNS exclude\
-   traffic routed to next region\
-   data already replicated

### ID Generator down

-   multiple workers\
-   fallback pool

### Analytics pipeline down

-   redirect 不受影響\
-   event 暫時丟失可接受

------------------------------------------------------------------------

## 9. Follow-up 問題 + 完整答案

### Q1. 如何避免 hot short codes？

-   使用 Redis / Edge cache 大幅減少 DB 命中\
-   對 custom alias 做限制（minimum length、reserved words）\
-   將 short_code hash 化再 map partition\
-   對 hot campaigns 做 pre-warm

------------------------------------------------------------------------

### Q2. Custom alias 如何 rate-limit？

-   Redis token bucket（基於 user_id）\
-   全局 IP rate-limit\
-   保留字管理\
-   企業可控 alias policy

------------------------------------------------------------------------

### Q3. 如何避免 cache stampede？

-   singleflight（只有第一個 miss 去 rebuild）\
-   隨機 TTL（避免同時過期）\
-   background refresh 模式\
-   soft TTL（延後實際過期時間）

------------------------------------------------------------------------

### Q4. 如何偵測惡意 redirect（phishing / malware）？

-   Safe Browsing API / URL reputation\
-   黑名單 / domain filter\
-   行為分析（abnormal traffic）\
-   中間警告頁（企業版可要求）

------------------------------------------------------------------------

### Q5. Edge cache 如何更新？

-   使用 version key：`short_code:version`\
-   update URL → version++\
-   或使用短 TTL + 強一致 DB\
-   或由管理後台觸發 edge invalidation

------------------------------------------------------------------------

### Q6. 如何支援企業 SSO？

-   SAML / OIDC\
-   組織 tenant_id 管理\
-   policy-level 控制（domain allowlist / TTL policy）

------------------------------------------------------------------------

### Q7. 如何避免 DB 過載？

-   依賴 Redis / Edge cache\
-   pre-warm 活動短碼\
-   rate-limit suspicious clients\
-   使用 async replication + fallback 讀取

------------------------------------------------------------------------

### Q8. 如何避免短碼 enumeration？

-   高 entropy ID（random / hashed）\
-   rate-limit 大量 404 流量\
-   add fake delay for repeated misses\
-   私有短碼需 ACL

------------------------------------------------------------------------

### Q9. 如何測試 multi-region failover？

-   Chaos engineering\
-   模擬 region outage\
-   模擬 network partition\
-   比對 failover 前後 redirect correctness\
-   自動化 regression

------------------------------------------------------------------------

### Q10. 如何做短碼 recycle？

-   過期後 + grace period\
-   使用 generation key\
-   日誌 analytics 分 generation 存放\
-   只對企業需求設定 recycle

------------------------------------------------------------------------

## 10. PlantUML（Hugo Shortcode）

{{< plantuml >}} 
@startuml

actor User
User --> "API Gateway" : Create / Redirect 
"API Gateway" --> "URL Service"
"URL Service" --> "Redis Cache" : get/set 
"URL Service" --> "NoSQL DB" : read/write 
"URL Service" --> "ID Generator" : generate ID
"URL Service" --> "Kafka" : click events 
"Kafka" --> "Stream Processor" : aggregate 
"Stream Processor" --> "Analytics DB" : store stats

@enduml 
{{< /plantuml >}}
---

## 1. URL Shortener（Bitly 類系統）

### 1.1 題目重述與假設

- 題目：設計一個類似 Bitly 的 URL 短網址服務。  
- 功能需求：  
  - 將長網址縮成短碼（例如：`https://foo...` → `https://short.ly/abc123`）  
  - 透過短碼 redirect 回原始 URL（HTTP 301/302）  
  - 支援自訂短碼（optional）  
  - 支援基本統計：點擊數、來源、時間分佈（可放進進階）  
- 非功能需求：  
  - 讀多寫少：redirect QPS 遠大於 create QPS  
  - 短碼要唯一且不可輕易被猜出整體情況  
  - latency：redirect P95 < 50ms（不含網路）  
  - 高可用（99.9%+）、可水平擴展  

### 1.2 高階架構說明

- 寫入路徑：  
  - Client 呼叫 Shorten API，帶長網址（+ 可選自訂 alias）  
  - API 產生短碼（編碼 / hash / sequence + base62），寫入 DB（`short_code → long_url`）  
  - 回傳完整短網址給使用者。  
- 讀取路徑：  
  - 使用者點 `https://short.ly/abc123` → 進入 Redirect Service  
  - 先查 cache（Redis），miss 再查 DB  
  - 取得 long_url 後回 HTTP redirect（302 或 301）  
  - 點擊資訊寫入 log / Kafka，後續做 offline 分析。  
- 儲存：  
  - 核心 mapping：`short_code` 為 primary key，可做水平分片（按字首或 hash）  
  - 熱門短碼全部在 cache。  

### 1.3 PlantUML 架構圖

{{< plantuml >}}
@startuml
title URL Shortener - High Level Architecture

actor User

rectangle "Frontend / Client" as FE
rectangle "Shorten API Service" as SVC_SHORTEN
rectangle "Redirect Service" as SVC_REDIRECT
rectangle "Cache (Redis)" as CACHE
database "URL Store (KV / NoSQL)" as DB
queue "Click Log (Kafka / Log Store)" as LOG
rectangle "Analytics Pipeline (batch/stream)" as ANALYTICS

User --> FE : create / open short URL

' Shorten path
FE --> SVC_SHORTEN : POST /shorten (long_url)
SVC_SHORTEN --> DB : insert(short_code → long_url)
SVC_SHORTEN --> FE : return short_url

' Redirect path
User --> SVC_REDIRECT : GET /{short_code}
SVC_REDIRECT --> CACHE : lookup(short_code)
CACHE --> SVC_REDIRECT : hit/miss
SVC_REDIRECT --> DB : lookup(short_code) # on miss
DB --> SVC_REDIRECT : long_url
SVC_REDIRECT --> User : HTTP 301/302 redirect

' Logging for analytics
SVC_REDIRECT --> LOG : click event
LOG --> ANALYTICS : consume events

@enduml
{{< /plantuml >}}

### 1.4 口頭講稿（約 2–3 分鐘）

> 這一題我會先把它理解成一個「讀多寫少」的 key-value service，key 是短碼，value 是長網址。  
> <br>
> 寫入路徑比較簡單：使用者呼叫 Shorten API，把長網址送進來。如果有自訂 alias，就先檢查是否已被佔用；如果沒有，就用一個全域遞增 ID 或隨機 64-bit ID，再編碼成 base62 當短碼。最後把 `short_code → long_url` 寫到 URL Store，回傳短網址給使用者。  
> <br>
> 讀取路徑是流量的主要來源：使用者點短網址，會打到 Redirect Service。Redirect Service 會先查 Redis cache，cache hit 就直接拿到 long_url 回傳 301/302 redirect；如果 cache miss 再查主 DB，把結果補回 cache。為了 統計統一處理，我會把每次點擊記錄成 click event 寫進 Kafka，由後端的 Analytics Job 做批次或即時統計。  
> <br>
> 資料分片方面可以以 short_code 的 hash 或 prefix 做 sharding，確保各個 DB 節點負載均衡。可用多個 region 部署 Redirect Service 和 cache，減少延遲並提升可用性。  

---