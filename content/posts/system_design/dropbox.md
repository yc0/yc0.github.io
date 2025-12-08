---
date: '2025-11-23T00:00:00+08:00'
draft: true
categories:
  - consistent hashing
  - system design
title: File Storage Service（Dropbox 類系統）
---
# Dropbox / Google Drive --- **Format 3C 完整版**

## （Hybrid：口語講稿 + Technical Deep Dive + Multi-Region Sync）
---
# 🎤 0. Opening（面試開場 45--60 秒）

我會把 Dropbox / Google Drive 類系統分成三層進行說明：

1.  **單 Region baseline 架構**：metadata + object storage + sync model\
2.  **Scalability 深度解析**：chunking、dedup、metadata sharding、change
    journal\
3.  **Multi-region global sync**：primary region、cross-region
    sync、conflict handling

整個系統的核心不是儲存檔案，而是**如何做到正確、高效率、可恢復的同步機制（synchronization
model）**。

------------------------------------------------------------------------

# 1. 問題定義與 Use Cases

使用者需求：

-   多裝置同步檔案（手機 / PC / 平板）\
-   單一裝置編輯檔案 → 所有裝置快速同步\
-   支援 offline editing\
-   支援 conflict resolve\
-   檔案版本管理\
-   支援大量小檔案、大檔案（\>1GB）

系統需保持：

-   **高 durability（不能遺失資料）**\
-   **可預測、強一致的 metadata**\
-   **高 QPS 的 sync event 推播能力**

------------------------------------------------------------------------

# 2. 功能性需求（Functional Requirements）

核心：

1.  Upload / Download\
2.  Multi-device sync\
3.  Versioning\
4.  Conflict resolution\
5.  Sharing\
6.  Directory management（rename, move, delete）

進階：

7.  Selective sync\
8.  LAN sync\
9.  Deep deduplication\
10. File preview / thumbnail service

------------------------------------------------------------------------

# 3. 非功能性需求 + Capacity & Performance 估算

## 3.1 Performance Targets

  行為                     延遲
  ------------------------ --------------
  metadata update          P95 \< 150ms
  sync event propagation   \< 5 秒
  chunk upload             可容忍數秒

## 3.2 QPS & Order-of-Magnitude Estimation

假設：

-   50M daily active users\
-   每人每天平均 40 個 sync events

則：

    2B sync events / day ≈ 23k events/s
    峰值：100k–200k events/s

Metadata operations（如 rename/move）：

-   5M ops/day → \~60 ops/sec （峰值 1k--3k）

## 3.3 Storage Estimation

假設：

-   500M users
-   平均每人 10GB

```
    500M * 10GB = 5 exabytes (raw)
```

透過 chunk-level dedup：

-   儲存量可下降 50--90%
-   Network 傳輸也大量減少

------------------------------------------------------------------------

# 4. 系統架構（Single-Region Baseline）

### Core Components

1.  **Metadata Service（strong consistency）**\
2.  **Metadata DB（SQL sharded / NoSQL）**\
3.  **Object Storage（chunk-based, immutable）**\
4.  **Sync Change Journal**\
5.  **Sync Service（增量同步）**\
6.  **Notification Service（push events）**\
7.  **Client Sync Agent（local diff engine）**

------------------------------------------------------------------------

# 5. Component Deep Dive

## 5.1 Chunking & Dedup（核心）

使用固定長度（4MB）或 Rabin Fingerprint 可變長 chunk。

### 優點：

-   減少上傳量（只上傳新增 chunks）\
-   Global dedup（跨使用者共享相同 chunks）\
-   支援 resumable upload

### Chunk Metadata

    chunk_id (hash)
    size
    checksum
    physical location

### File Version Metadata

    file_id
    list_of_chunks
    mtime
    etag
    version

------------------------------------------------------------------------

## 5.2 Metadata Service（強一致主體）

管理：

-   folder tree（inode 結構）\
-   file attributes\
-   version history\
-   ACL / sharing metadata

Rename / move 僅修改 metadata pointer → O(1)

Sharding：

-   依 user_id 或 namespace 分片\
-   大用戶（大量檔案）可單獨分片

------------------------------------------------------------------------

## 5.3 Sync Change Journal（Dropbox 的靈魂）

每個 user 有：

    seq_id: monotonic increasing integer
    entries: (seq_id, file_id, operation, version)

裝置同步：

    client → server: give me changes since seq = X
    server → client: list of changes

特性：

-   增量同步（不需傳整棵 folder tree）\
-   crash-safe\
-   conflict detection

------------------------------------------------------------------------

## 5.4 Notification Service

負責推播 "有更新" 事件。

技術選項：

-   WebSocket\
-   Long polling\
-   Pub/Sub（Kafka / Redis Stream）

------------------------------------------------------------------------

# 6. 核心流程

## 6.1 Upload File Workflow

1.  Client 偵測檔案變更（local FS watcher）\
2.  切 chunk + 計算 hash\
3.  問 server 哪些 chunks 已存在\
4.  上傳 missing chunks\
5.  更新 metadata\
6.  journal append\
7.  push 通知其他裝置

------------------------------------------------------------------------

## 6.2 Multi-device Sync Workflow

1.  Client 啟動\
2.  送出 last seen seq\
3.  Server 回傳增量 changes\
4.  Client 套用變更\
5.  若發生 conflict → 建立 "conflicted copy"

------------------------------------------------------------------------

## 6.3 Sharing Workflow

-   public link：anonymous object fetch\
-   permission-based share：folder pointer share\
-   shared folder = shared metadata namespace

------------------------------------------------------------------------

# 7. Multi-Region Architecture（進階）

------------------------------------------------------------------------

## 7.1 Why multi-region is complicated?

因為：

-   metadata **需要強一致**，跨 region consensus 成本極高\
-   chunk storage **可 eventual**（immutable）\
-   sync journal 需要按順序、不能亂序

------------------------------------------------------------------------

## 7.2 Architecture Pattern A：Global Strong Consistency（Google Drive Style）

使用：

-   Spanner\
-   TrueTime API\
-   globally ordered metadata updates

優點：

-   無亂序問題\
-   sharing、rename、move 非常乾淨

缺點：

-   貴\
-   寫入延遲略高

------------------------------------------------------------------------

## 7.3 Architecture Pattern B（更普遍）：**Per-user Primary Region**

每個 user 的 metadata：

-   只位於一個 primary region（如 US-East）\
-   所有 sync 都往 primary region 送\
-   若 user 移動地理位置 → 可 migrate primary region

### 優點：

-   避免 global coordination\
-   metadata consistency 不會亂\
-   cross-user sharing 時才需要跨區溝通

------------------------------------------------------------------------

## 7.4 Chunk Storage Multi-Region

Chunks 屬 immutable：

-   可在 local region 儲存副本\
-   用 CDN 加速下載\
-   更改 chunk references（metadata）就能同步版本

------------------------------------------------------------------------

# 8. Scalability Engineering

## Metadata Scaling

-   Sharding by user\
-   Using SQL（MySQL shard）或 NoSQL（FoundationDB / Cassandra）\
-   Folder caching

## Sync Journal Scaling

-   append-only log\
-   separate per-user shard\
-   queries independent

## Object Storage Scaling

-   chunk immutable\
-   S3-like storage\
-   low-cost replication

------------------------------------------------------------------------

# 9. Failure Scenarios & Recovery

### Metadata DB crash

-   replicate + consensus\
-   WAL-based recovery

### Journal corruption

-   checksum\
-   shadow log\
-   snapshot based recovery

### Chunk storage outage

-   fallback to replica\
-   long-term: erasure coding

------------------------------------------------------------------------

# 10. Follow-up Questions + 標準回答

------------------------------------------------------------------------

### Q1. 如何避免 metadata hot partition？

**A：**

-   shard by user\
-   large users 分裂 shard\
-   cache frequently accessed directory listing\
-   batch operations

------------------------------------------------------------------------

### Q2. 如何處理大量小檔案（100k+ files）？

**A：**

-   batch sync events\
-   compact directory representation\
-   Bloom filter avoid unnecessary fetch\
-   reduce metadata calls

------------------------------------------------------------------------

### Q3. 如何支援 offline editing？

**A：**

-   local delta log\
-   conflict detection with version vector\
-   reconcile on reconnect

------------------------------------------------------------------------

### Q4. rename / move 為何是 O(1)？

**A：**

-   metadata pointer update\
-   chunk 不變\
-   no physical movement

------------------------------------------------------------------------

### Q5. 如何處理 1GB+ 大檔案？

**A：**

-   multipart upload\
-   chunk resume\
-   speculative parallel upload

------------------------------------------------------------------------

### Q6. 如何達成 global dedup？

**A：**

-   chunk hash\
-   index table for chunk store\
-   salted hash to prevent privacy leak

------------------------------------------------------------------------

### Q7. multi-region conflict 如何處理？

**A：**

-   per-user region → avoid most conflict\
-   shared folder uses version vector or timestamp ordering\
-   if conflict → auto create conflict copy

------------------------------------------------------------------------

# 11. PlantUML（Hugo Shortcode）

{{< plantuml >}} 
@startuml 
actor Client
Client --> "Sync Service" : upload/download diff 
Client --> "Notification Service" : subscribe
"Sync Service" --> "Metadata Service" : update metadata 
"Metadata Service" --> "Metadata DB" : read/write
"Sync Service" --> "Object Storage" : upload chunks 
"Metadata Service" --> "Change Journal" : append changes "Notification Service" --> Client : notify updates

@enduml 
{{< /plantuml >}}

---
## 2. File Storage Service（Dropbox 類系統）

### 2.1 題目重述與假設

- 題目：設計類 Dropbox / Google Drive 的雲端檔案儲存與同步服務。  
- 功能需求：  
  - 上傳 / 下載檔案  
  - 多裝置同步（桌機 / 手機）  
  - 版本歷史（可以回復舊版本）  
  - 分享連結 / 權限控制（進階）  
- 非功能需求：  
  - 可儲存大量檔案（PB 級）  
  - 高耐久性（11 個 9 等級）  
  - 跨 device eventual consistency 可接受  
  - 上傳 / 下載 throughput 以及斷線恢復  

### 2.2 高階架構說明

- Client 會把檔案切成 fixed 或 variable-size chunks，上傳至 Storage nodes。  
- Metadata service 管理：folder 結構、檔案版本、每個版本對應的 chunk 列表。  
- 寫入：  
  - Client → Upload Service：上傳 chunks，計算 hash 做 dedup。  
  - 寫入 Object Store（如 S3 / HDFS / 自建）。  
  - Metadata Service 紀錄 file → [chunk hashes]。  
- 讀取：  
  - Client 向 Metadata Service 查詢某檔案版本的 chunk 列表，再從 Storage 拿 chunks，組合成檔案。  
- Sync：  
  - Client 有 local index，定期與 Metadata Service 比較差異，進行增量同步。  

### 2.3 PlantUML

{{< plantuml >}}
@startuml
title File Storage Service - High Level Architecture

actor User
rectangle "Client (Sync Agent)" as CLIENT

rectangle "API Gateway" as API
rectangle "Metadata Service" as META
database "Metadata DB (files, versions, chunks)" as METADB

rectangle "Upload Service" as UP
rectangle "Download Service" as DOWN
cloud "Object Storage (Chunks, immutable)" as STORE

queue "Change Log (Events)" as CHANGELOG

User --> CLIENT : file changes
CLIENT --> API : upload/download requests

API --> UP : upload file
UP --> META : get/alloc file_id
UP --> STORE : upload chunks
UP --> META : write file metadata
(path, version, chunk list)
META --> METADB

API --> DOWN : download file
DOWN --> META : get file metadata
META --> METADB
DOWN --> STORE : fetch chunks
STORE --> DOWN
DOWN --> CLIENT : file data

META --> CHANGELOG : file change events
CHANGELOG --> CLIENT : sync updates

@enduml
{{< /plantuml >}}

### 2.4 口頭講稿（約 2–3 分鐘）

> 我把雲端硬碟分成兩塊：一個是「巨大而便宜的物理儲存（Object Storage）」，另一個是「比較小但很關鍵的 Metadata Service」。  
> <br>
> 當使用者上傳檔案時，Client 會先把檔案切成 chunks，計算每個 chunk 的 hash，避免重複上傳相同內容。上傳流程透過 Upload Service 把 chunks 寫進 Object Store，並且在 Metadata Service 註冊一個新的檔案版本，紀錄這個版本用到哪些 chunks。這樣可以在使用者改動部分內容時，只重新上傳變動的 chunks。  
> <br>
> 下載則是先問 Metadata Service 拿到某個檔案版本對應的 chunk 列表，再向 Object Store 抓取並在 Client 端組裝。  
> <br>
> 多裝置同步依賴 Change Log：Metadata Service 將每個檔案變動寫進一個 log stream，Client 端會追這個 log，看到有新的版本或刪除動作就同步本地資料夾。衝突時可以依 timestamp 或用 three-way merge 策略處理。  

---
