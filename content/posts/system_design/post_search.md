---
date: '2025-11-27T00:00:00+08:00'
draft: true
categories:
  - system design
title: Post Search（社群貼文搜尋）
---
## 6. Post Search（社群貼文搜尋）

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