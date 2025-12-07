---
date: '2025-12-02T00:00:00+08:00'
draft: true
categories:
  - system design
title: Ad Click Aggregator
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