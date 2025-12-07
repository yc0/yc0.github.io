---
date: '2025-11-26T00:00:00+08:00'
draft: true
categories:
  - system design
title: Messaging System（WhatsApp / Messenger 類）
---
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

## 6. Post Search（社群貼文搜尋）

> ✅ 詳細版請參考你之前的 `post_search_full.*`，這裡是濃縮版。

### 6.1 問題與需求

- 全文搜尋貼文 content（title + body）  
- 支援 filters（時間、作者、board、visibility）  
- 支援排序（relevance / time）  
- Read-heavy，寫入 async，eventual consistency 可接受。  

### 6.2 簡化版 PlantUML（高階）

{{< plantuml >}}
@startuml
title Post Search - High Level Architecture (Simplified)

actor User
rectangle "Frontend" as FE
rectangle "Search API Service" as API
rectangle "Query Cache" as QC
rectangle "Search Cluster (Inverted Index)" as SC
rectangle "Post Cache" as PC
database "Post DB" as DB
rectangle "Post Service" as POST
queue "Event Log (Kafka)" as LOG
rectangle "Indexers" as IDX

User --> FE : search / create post
FE --> API : search query
API --> QC : check cache
QC --> API : hit/miss
API --> SC : full-text query
SC --> API : doc_ids
API --> PC : fetch hot posts
API --> DB : fetch post details
API --> FE : results

FE --> POST : create / update post
POST --> DB : write post
POST --> LOG : publish post-events
LOG --> IDX : consume
IDX --> SC : update index

@enduml
{{< /plantuml >}}

### 6.3 口頭講稿（簡版 2 分鐘）

> 我會把 Post Search 設計成一個 read-heavy、async indexed 的搜尋系統。  
> <br>
> 寫入時，貼文先透過 Post Service 寫入主 DB，成功後將事件丟給 Kafka 這類 Event Log，由多個 Indexer workers 非同步地做分詞與倒排索引更新。這樣發文 latency 不會因 index 更新而被拉高。  
> <br>
> 搜尋時，Search API 先查 Query Cache，miss 再打 Search Cluster（Elasticsearch/OpenSearch），取得一批 doc_ids 後到 Post Cache 或 DB 補齊貼文內容。Index 裡會內嵌過濾欄位，例如時間、作者、board、visibility，讓大部分權限/條件過濾在 search engine 層完成。  
> <br>
> 排序一開始可以用 BM25 + time decay，之後再引入 engagement signals 和 personal ranking。  

---

## 7. Online Judge / Coding Platform（LeetCode 類）

### 7.1 題目重述與假設

- 題目：設計一個線上刷題 / 線上評測系統（像 LeetCode）。  
- 功能需求：  
  - 使用者提交程式碼，系統在 sandbox 中編譯 / 執行 / 判斷結果  
  - 顯示執行結果、錯誤輸出、耗時與記憶體  
  - 題目管理、測資管理  
- 非功能需求：  
  - 隔離性：每個 submission 不得影響平台安全  
  - 延遲：允許數秒～十數秒等待  
  - 可水平擴展評測 worker  

### 7.2 高階架構說明

- Submission 進入 queue，由多個 Judge Worker 消費。  
- Worker 在 sandbox（container / VM）中拉題目測資，編譯並執行使用者程式。  
- 結果寫回 DB，並透過 WebSocket / polling 通知前端。  

### 7.3 PlantUML

{{< plantuml >}}
@startuml
title Online Judge - High Level Architecture

actor User
rectangle "Web UI" as UI
rectangle "API Server" as API
database "Problem & Submission DB" as DB

queue "Submission Queue" as SUBQ
rectangle "Judge Worker Pool" as WORKERS
cloud "Sandbox Environment (Docker/VM)" as SANDBOX
database "Test Case Store" as TESTS

User --> UI : submit solution
UI --> API : POST /submission
API --> DB : create submission(record)
API --> SUBQ : enqueue submission_id

SUBQ --> WORKERS : dequeue submission
WORKERS --> DB : load submission & problem meta
WORKERS --> TESTS : fetch test cases
WORKERS --> SANDBOX : compile & run
SANDBOX --> WORKERS : result (AC/WA/TLE/MLE/...)
WORKERS --> DB : update submission result

UI --> API : GET /submission/{id}
API --> DB : query result
DB --> API
API --> UI : result + logs

@enduml
{{< /plantuml >}}

### 7.4 口頭講稿（約 2–3 分鐘）

> 我會把 Online Judge 當成一個「非即時但要高度隔離的批處理系統」。  
> <br>
> 使用者在 Web UI 提交程式碼，API Server 建立 submission record，將 submission_id 丟到 Submission Queue。Judge Worker Pool 從 queue 取出任務，根據 problem id 去 Test Case Store 抓測資，然後在隔離好的 sandbox 中完成 compile & run。  
> <br>
> Sandbox 可以用 Docker / Firecracker 這類技術，每次提交在新的容器環境下執行，確保安全與資源限制。執行完後 Worker 寫回結果到 DB。使用者可以透過 polling 或 WebSocket 查詢結果。  
> <br>
> 整個系統可以透過增加 Worker 節點來水平擴展，submission queue 本身具備 buffer 能力。  

---

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

## 9. Web Crawler

### 9.1 題目重述與假設

- 題目：設計一個可擴展的 Web Crawler。  
- 功能需求：  
  - 從 seed URLs 開始，遵守 robots.txt，抓取頁面內容  
  - 控制抓取頻率，避免對單一網站過載  
  - 支援 URL 去重、內容存儲、後續索引使用  
- 非功能需求：  
  - 高吞吐（每秒多頁）  
  - 可根據 domain 做 politeness control  
  - 容錯與重試  

### 9.2 高階架構說明

- Frontier：待抓取 URL 隊列，可按 domain 分 bucket。  
- Fetcher：從 Frontier 拿 URL，發 HTTP request 抓內容。  
- Parser：解析 HTML，抽出文字與新 URL，寫入 content store 與 dedup system。  
- robots.txt & politeness：每個 domain 有自己的抓取頻率與延遲。  

### 9.3 PlantUML

{{< plantuml >}}
@startuml
title Web Crawler - High Level Architecture

rectangle "URL Frontier (priority queues by domain)" as FRONTIER
rectangle "Fetcher Workers" as FETCH
rectangle "Parser & Extractor" as PARSER
database "Content Store (raw HTML / parsed)" as CONTENT
database "URL Seen Store (dedup)" as SEEN
rectangle "Robots & Politeness Manager" as ROBOTS

FRONTIER --> FETCH : pop next URL
FETCH --> ROBOTS : check robots.txt / delay
ROBOTS --> FETCH : allowed / wait

FETCH --> CONTENT : store raw HTML
FETCH --> PARSER : send HTML

PARSER --> CONTENT : store parsed content
PARSER --> SEEN : check / add new URLs
SEEN --> FRONTIER : enqueue unseen URLs

@enduml
{{< /plantuml >}}

### 9.4 口頭講稿（約 2–3 分鐘）

> Crawler 的核心是 Frontier 管理、去重與 politeness。  
> <br>
> Frontier 可以是按 domain 分桶的 priority queue，每個 domain 有自己的抓取速率控制，搭配 Robots & Politeness Manager 來判斷是否可以抓取，以及下一次抓取時間。Fetcher 從 Frontier 拿 URL，先檢查 robots 和訪問間隔，合適時發 HTTP request 抓 HTML。  
> <br>
> Parser 負責解析 HTML，抽取文字、標題、連結等結構化資訊，寫入 Content Store，同時將頁面上的連結送入 Seen Store 做 dedup。未出現過的 URL 才會被丟回 Frontier。  
> <br>
> 整體可以水平擴展：多個 Fetcher / Parser 節點，共享 Frontier 和 Seen Store。對於失敗的 URL，可加 retry 計數與 backoff。  

---

## 10. Ad Click Aggregator

### 10.1 題目重述與假設

- 題目：設計一個即時廣告點擊聚合系統，用於統計 CTR、展示量、點擊量。  
- 功能需求：  
  - 實時接受 impression / click 事件  
  - 依照 campaign / ad / time window 聚合計數  
  - 支援 dashboard 查詢最近幾分鐘～幾小時的統計數據  
- 非功能需求：  
  - 高吞吐（每秒數十萬事件）  
  - 允許輕微延遲（數秒以內）  
  - 準確度需求可討論（exactly-once / at-least-once）  

### 10.2 高階架構說明

- Event Ingress：前端 / SDK 上報 impression & click 到 Ingestion API。  
- 事件寫入 Kafka，後端有 streaming job（Flink/Spark Streaming）做聚合（per ad, per minute）。  
- 聚合結果寫入 OLAP store（如 Druid / ClickHouse / BigQuery）供 dashboard 查詢。  

### 10.3 PlantUML

{{< plantuml >}}
@startuml
title Ad Click Aggregator - High Level Architecture

actor User
rectangle "Web / App" as CLIENT

rectangle "Ingestion API" as INGEST
queue "Event Stream (Kafka)" as KAFKA

rectangle "Stream Processor (Flink / Spark)" as STREAM
database "Aggregated Store (OLAP: Druid/ClickHouse)" as OLAP
database "Raw Event Store (HDFS / Object Store)" as RAW

rectangle "Analytics Dashboard" as DASH

User --> CLIENT : view ad / click ad
CLIENT --> INGEST : send impression/click event
INGEST --> KAFKA : append event
INGEST --> RAW : optional raw dump

KAFKA --> STREAM : consume events
STREAM --> OLAP : upsert counters by ad, campaign, time window

DASH --> OLAP : query metrics
OLAP --> DASH : stats

@enduml
{{< /plantuml >}}

### 10.4 口頭講稿（約 2–3 分鐘）

> Ad Click Aggregator 本質上是一個流式資料處理系統。  
> <br>
> 使用者在 App 或網頁看到廣告、點擊廣告時，SDK 會將 impression 和 click event 傳到 Ingestion API。Ingestion API 把事件寫進 Kafka，並可選擇同步寫一份 raw log 到 Object Store 以便離線分析。  
> <br>
> 後端有一個流處理任務（例如 Flink / Spark Streaming），從 Kafka 消費這些事件，按照 campaign、ad_id 以及時間窗（例如 1 分鐘）做聚合，將結果寫入 OLAP 資料庫。Dashboard 則直接查 OLAP，取得 CTR、展示量、點擊量。  
> <br>
> 與 exactly-once 的關係可以透過 Kafka + Flink 的 checkpoint 與兩階段提交來靠近實作，若業務容忍輕微誤差，也可以選擇 at-least-once + 偶爾重算。  

---