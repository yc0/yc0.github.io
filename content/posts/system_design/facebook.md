---
date: '2025-11-25T00:00:00+08:00'
draft: true
categories:
  - system design
title: News Feed（Facebook / Instagram 類）
---
# Feed System Design 
---

## 🎤 0. Opening（60–90 秒口語講稿）

這題我要設計的是一個類似 **Instagram Home Feed / Explore Feed** 的系統。  
目標不是「單純顯示幾張圖片」，而是要支援：

- 上億使用者  
- 每天數十億張貼文（photos / videos）  
- 每次打開 App 都要在幾百毫秒內回傳一個排序好的 feed  
- 同時還要支援 Stories、Reels、廣告（可以先簡化）

我會把整個設計拆成三個層次來說：

1. **Baseline：單 user 的追蹤 feed（following feed）**  
   - 使用者追蹤其他人，打開 App 時看到朋友 / 追蹤對象的最新貼文。  
2. **Feed Generation & Ranking：**  
   - feed 資料從哪裡來？  
   - 用什麼模型排序？  
   - **fan-out vs fan-in**（寫時擴散 vs 讀時聚合）設計取捨。  
3. **Scalability & Multi-region：**  
   - 如何支援數億 user、全球多資料中心？  
   - cache、sharding、冷/熱資料分層。  

---

## 1. 問題定義（Problem Definition）

我們的系統要提供至少兩種核心 feed：

1. **Home Feed（Following Feed）：**  
   - 使用者打開 App → 看到「自己追蹤的帳號」發的貼文，通常依時間 + 排序模型排列。  

2. **Explore / Recommendation Feed：**  
   - 顯示使用者沒有追蹤的帳號貼文，但對他可能有興趣。  
   - 使用排序 / recommendation 模型。

在多數面試情境，我會先 **專注於 Home Feed（Following feed）** 做架構與擴充，  
Explore Feed 則當作「同樣 feed pipeline，但 upstream 換成推薦系統」。

---

## 2. 功能性需求（Functional Requirements）

### 2.1 核心功能

1. **發布貼文（Post / Photo / Video）**
   - 使用者可以上傳圖片 / 影片 / 說明文字 / 標籤（hashtags）。  
   - 支援多張圖片（carousel）可暫時簡化成「一篇貼文一個主要內容」。  

2. **追蹤 / 取消追蹤（Follow / Unfollow）**
   - 使用者可以追蹤其他帳號。  
   - Follow graph 會直接影響 Home Feed 的來源。  

3. **查看 Home Feed（Following Feed）**
   - 打開 App 或下拉刷新時，系統要回傳一串排序好的貼文列表。  
   - 每次回傳前 N 筆，例如 20～50 篇，支援 infinite scroll / pagination。  

4. **互動行為（Engagement）**
   - Like / Unlike  
   - Comment  
   - Share / Re-share / Send to friends  

5. **基於互動的排序（Ranking）**
   - 根據使用者與 content 的互動歷史（like、停留時間、點擊）調整排序。  
   - 不只依照時間排序，而是 **「Relevant + Recent」** 的組合。  

---

### 2.2 進階功能（Optional，可視時間加碼）

6. **Stories / Reels**
   - 可視為另一條 feed pipeline，結構相似。  

7. **Ads / Sponsored Posts**
   - 在 feed 中間插入廣告貼文（ad ranking）。  

8. **Mute / Block / Hide / Report**
   - 使用者可隱藏某些貼文或封鎖特定帳號。  

9. **多裝置同步**
   - 在手機 / Web 打開 feed，看到的排序應該基本一致（或相近）。  

---

## 3. 非功能性需求（Non-functional Requirements）

### 3.1 Latency（延遲）

| 功能 | 目標延遲 |
|------|----------|
| 打開 Home Feed 首屏 | P95 < 200–300 ms（後端處理時間） |
| 無限捲動載入下一頁 | P95 < 200 ms |
| 發布貼文後出現在自己的 feed | 1–5 秒（可接受小延遲） |
| 發布貼文出現在其他人 feed | 1–10 秒（eventual 即可） |

重要觀念是：  
**Feed 顯示可以稍微延遲，但不能卡很久；排序與推薦可以稍微犧牲強一致。**

---

### 3.2 Throughput & Scale（粗略估算）

假設：

- 1B 註冊使用者  
- 200M Daily Active Users（DAU）  
- 每人每日打開 App 10 次、每次拉 3 頁 feed  

粗略計算 feed read QPS：

```
200M users * 10 打開 * 3 頁 = 6B feed views/day
6B / 86400 ≈ 69,444 feed page views per second (avg)
峰值可達 3–10 倍：200k–700k QPS
```

發布貼文寫入 QPS（Post）相對較小，但每篇貼文可能 fan-out 給數百～數萬 followers。

---

### 3.3 Consistency（Consistency Requirements）

| 資料 | 一致性需求 |
|------|-------------|
| 貼文內容（Post data） | 一旦發佈需具備高耐久性（durability），可用最終一致 |
| Follow Graph | 對 feed 來說需 **接近即時**，但可接受毫秒～數秒延遲 |
| Feed 排序 | 強一致困難且成本高，一般採 **eventual with bounded staleness** |
| Like / View Count | 可略有延遲，不需強一致（反正是「近似」數字） |

---

### 3.4 Availability & Durability

- Feed read 寧可「稍舊（slightly stale）」，也要高可用（高 availability）。  
- Post / Media 要有 **高 durability**（多副本 / 多 DC）  
- 不能因為某個 ranking 模型掛掉，就讓 feed 完全不可用 → 需要 degrade 策略，例如退回 time-based 排序。

---

## 4. 界定範圍（Scope Clarification）

面試時間有限，整個 Instagram 非常龐大，所以我會：

1. **優先專注：Home Feed（Following-based feed）**
   - 貼文產生 → 儲存 → feed 生成 → 排序 → 回傳。  
2. Explore / Recommendation Feed  
   - 當做「同一套 feed delivery pipeline，但 upstream 來源改成推薦系統」。  

另外我會簡化 / 不重點描述的部分：

- Full-blown ML pipeline（特徵工程、模型訓練）  
- Ads bidding / auction system  
- Stories / Reels 的多媒體專用特殊行為  

但我會在答題中提到：  
> 若有時間，我可以進一步講針對 Explore / Ads 的 ranking pipeline 與模型特化。

---

## 5. 高階資料模型（Entities Overview）

主要實體（Entities）：

1. **User**
   - user_id  
   - profile  
   - settings（語言 / 隱私 / mute 列表）

2. **Post**
   - post_id  
   - author_id（user）  
   - media_urls（圖片 / 影片）  
   - caption / hashtags  
   - created_at / updated_at  
   - visibility（public / private / close-friends）

3. **Follow Relationship（Follow Graph）**
   - follower_id  
   - followee_id  
   - created_at  

4. **Engagement**
   - likes（user_id, post_id, created_at）  
   - comments  
   - saves / shares  

5. **Feed Item（可能為預計算結果）**
   - user_id（feed owner）  
   - post_id  
   - score（ranking score）  
   - generated_at  

---

## 6. High-level Feed Generation 模型總覽

在設計 Instagram Feed 時，有一個重要的核心設計抉擇：

> **Fan-out on write vs Fan-out on read**

### 6.1 Fan-out on Write（寫入時擴散）

當使用者 A 發布一篇貼文時：

- 馬上將這篇貼文「推送」到所有 followers 的 feed inbox 中。  
- 之後 followers 打開 feed，只需從自己的 inbox 讀出貼文（讀取很快）。

優點：

- 讀取非常快（feed read 只需從本地 inbox 拿資料）。  
- 讀 route 很簡單、容易 cache。

缺點：

- 對於擁有超大量 followers 的帳號（例如明星 / 名人）  
  - 一篇貼文要 fan-out 到 **上千萬 / 上億 feed**，非常昂貴。  
- 還要處理：
  - 某些 followers 已經不活躍  
  - 寫入風暴（write amplification）

---

### 6.2 Fan-out on Read（讀取時聚合）

當 follower 打開 feed 時：

- 即時 query：  
  - 先查出我追蹤了哪些人  
  - 再對這些人查詢他們的最新貼文  
  - 最後合併、排序後回傳。

優點：

- 發布貼文非常便宜（只寫一次 Post）。  
- 不用擔心大 V 帳號爆炸式寫入。

缺點：

- 讀取非常昂貴：  
  - 需要 query 很多 authors 的貼文  
  - 需要 sort / merge / ranking  
  - 延遲難壓低，尤其當 user 追蹤數量很多（例如 follow 上千人）。

---

### 6.3 Hybrid Model（Instagram / Twitter 實際常用）

大公司通常用 **混合策略**：

1. 對「普通用戶」採用 **fan-out on write**：  
   - followers 數量有限（例如幾百 / 幾千）  
   - 推送到每個 follower 的 feed inbox 是可接受的。  

2. 對「超大 V / 名人帳號」採用 **lazy / on-read 聚合**：  
   - 不主動 fan-out 給所有 followers。  
   - 在 followers 打開 feed 時，再即時計算 / 合併「大 V 貼文」部分。

面試時點出這個 hybrid 模型，是一個很好的加分點。

---

## 7. High-level Flow（從發文到出現在 feed）

可以先口頭講，再在後續 Part 2 畫架構圖與時序圖。

### 發文流程（Writer-side）

1. 使用者 A 上傳圖片 / 影片和文字 → Post Service  
2. Post Service 儲存 post metadata + media（S3 / Blob storage）  
3. Post 寫入 timeline storage（例如按作者分桶的 time-ordered log）  
4. 觸發事件：

```
"post_created" event → 送入 Kafka / PubSub
```

5. Feed Fan-out Worker 從事件流中讀取「post_created」事件：
   - 對 author 的 followers 列表做迭代  
   - 把 post_id 插入各個 follower 的 feed inbox（inbox table / Redis list）  
   - 對超大 V 會採取特殊策略（跳過或部分 fan-out）

---

### 讀取流程（Reader-side）

1. 使用者 B 打開 Home Feed → Feed Service  
2. Feed Service 做的事：

   - 從 B 的 feed inbox（cache / DB）讀取一批 post_ids  
   - 取得對應的 post metadata（批量查詢）  
   - 呼叫 Ranking Service：
     - 基於互動歷史（like/停留時間）、相似度、freshness  
     - 計算每個 post 的 score  
   - 把排序後的前 N 筆回傳給客戶端  

3. 客戶端顯示，並在 background 預抓下一頁。

---

## 8. Part 1 小結（後續銜接到 Part 2）

到這裡，我已經：

- 定義清楚 Instagram Feed 的 **核心問題與 Use Cases**  
- 梳理功能性 / 非功能性需求  
- 說明資料尺度（QPS / DAU / feed views）  
- 引出最關鍵的架構抉擇：  
  - **fan-out on write、fan-out on read、hybrid**  
- 給出發文 → fan-out → 讀取 → ranking 的高階流程

在面試中，這一 Part 大概會講 8–10 分鐘，  
接下來 Part 2 我會畫架構圖，詳細拆解各個 service 與資料存儲（Post Store、Feed Store、Graph Store、Cache、Streaming Pipeline）。

---

> ✅ 這份檔案可以直接存成 `instagram_part1_opening_requirements.md`  
>  接下來如果你輸入：  
>  **Next: Part 2**  
>  我會用同樣格式提供：  
>  **Architecture + Components Deep Dive（附 PlantUML、Hugo-safe）**
---
## Architecture + Component Deep Dive（Hugo-safe, no backticks）

# 1. High-level Architecture Overview

在 Part 1 我已經定義了需求與 fan-out/fan-in 模型，  
Part 2 會專注在「服務拆分與資料流」，也就是：

- 我們有哪些核心 Service？  
- 各自的責任是什麼？  
- 資料怎麼從 Post → Feed → 排序 → 回到使用者手上？

---

## 1.1 核心服務清單（按職責分組）

### A. Edge & User-facing

1. **API Gateway / Edge Service**  
   - 所有客戶端（App / Web）請求的入口  
   - 做驗證（Auth）、流量控制（Rate limiting）、版本路由（A/B test）

2. **User Service**  
   - 使用者基本資料（暱稱、頭像、設定）  
   - 黑名單 / 隱私設定（private account, blocked users）

---

### B. 内容與媒體

3. **Post Service**  
   - 接收發文請求（圖片 / 影片 / caption / hashtags）  
   - 寫入 Post Store（metadata）  
   - 產生 post_id  
   - 發佈 post_created 事件（推給 feed pipeline）

4. **Media Service / CDN**  
   - 實際儲存二進位媒體（圖片、影片）到 Blob Storage：  
     - S3 / GCS / HDFS  
   - 透過 CDN 發佈（快取、邊緣節點）

---

### C. 社交關係

5. **Social Graph Service（Follow Graph）**  
   - 管理 follower / followee 關係  
   - 提供 API：  
     - get_followers(user_id)  
     - get_followees(user_id)  
   - 儲存於：  
     - Graph DB（Neo4j / custom）  
     - 或 Sharded SQL / KV（例如 user_id → list of followees）

---

### D. Feed Pipeline（重點）

6. **Feed Fan-out Service（Write Path）**  
   - 消費 post_created 事件  
   - 查詢該作者的 followers 列表  
   - 將 post_id 寫入 followers 的 feed inbox（Feed Store）  
   - 對大 V / 名人使用特別策略（不完全 fan-out）

7. **Feed Read Service（Read Path）**  
   - 使用者打開 Home Feed 時被呼叫  
   - 從 Feed Store 中讀取該 user 的 feed entries  
   - 整合 Post metadata  
   - 呼叫 Ranking Service 做排序  
   - 回傳前 N 筆結果（支援 pagination）

8. **Ranking Service**  
   - 接收 feed candidate（user_id + list of post_ids）  
   - 基於 user / content 特徵計算 score  
   - 回傳排序後的貼文列表  
   - 可支援不同 feed 模式（Home / Explore / Reels）

---

### E. Engagement 與 Analytics

9. **Engagement Service（Like / Comment / Save / Share）**  
   - 管理互動資料（按讚、留言、收藏）  
   - 將事件寫入 Engagement Store + 送到 Kafka 給 ML pipeline

10. **Logging / Metrics / Analytics Pipeline**  
   - 所有互動、曝光（impression）、停留時間（dwell time）  
     都會產生 event，送到 Kafka / PubSub  
   - downstream 用來做：  
     - A/B 測試分析  
     - Ranking 模型訓練  
     - Fraud / Spam 檢測

---

## 1.2 核心儲存（Storage 層）

1. **Post Store**  
   - 存放貼文 metadata  
   - 常見實作：  
     - Sharded NoSQL（Cassandra / HBase / Bigtable）  
   - 按 author_id 分 shards：  
     - 每個作者有自己的 time-ordered posts list

2. **Media Blob Store + CDN**  
   - 圖片 / 影片實際二進位內容存放處  
   - 透過 CDN 提供就近快取

3. **Social Graph Store**  
   - follower / followee  
   - 可用：  
     - Sharded KV（user_id → followee list）  
     - 或 Graph DB 搭配 cache

4. **Feed Store（Feed Inbox）**  
   - 每個 user 有一個「inbox」，裡面放 post_id 列表 + score / timestamp  
   - 可以用：  
     - Redis / Aerospike / RocksDB + index  
   - 類似：  
     - user_id → [ (post_id, inserted_at, pre_score), ... ]

5. **Engagement Store**  
   - like / comment / save 等互動記錄  
   - 部分可存 SQL（for strong consistency）  
   - 部分可存 NoSQL + 事件流（for analytics）

---

# 2. 整體資料流程（從發文到顯示）

## 2.1 發文寫入（Write Path）

當一位使用者 A 發布新貼文：

1. Client → API Gateway → Post Service  
2. Post Service：  
   - 驗證 user  
   - 存 metadata 至 Post Store  
   - 觸發事件：

   ```
   event: post_created
   payload: { post_id, author_id, timestamp, ... }
   ```

3. 將 post_created event 推入 **Kafka / PubSub** topic，例如：  
   ```
   topic: post_created
   ```

4. **Feed Fan-out Service** 作為 consumer，從 `post_created` 讀取事件：  
   - 呼叫 Social Graph Service：  
     ```
     followers = get_followers(author_id)
     ```
   - 對每位 follower f 執行：  
     ```
     insert (f, post_id, created_at) into Feed Store (f 的 inbox)
     ```

5. 對於「粉絲數極多的大 V」：  
   - 可以選擇不立即 fan-out 到所有 followers，改為：  
     - 在 read path 時專門額外查詢「大 V posts」再合併進 feed。  

---

## 2.2 讀取 Feed（Read Path）

當使用者 B 打開 Instagram：

1. Client → API Gateway → Feed Read Service  
2. Feed Read Service：  
   - 從 Feed Store 讀取 B 的 inbox：

   ```
   candidate_entries = get_feed_inbox(user_id=B, limit=K, cursor=...)
   // 例如拿 200 筆後再做排序，最後回傳前 20 筆
   ```

   - 批量查詢 Post Store 拿 metadata：  
     ```
     posts = batch_get_posts(candidate_entries.post_ids)
     ```

   - 呼叫 Ranking Service：  
     ```
     ranked_posts = ranking_service.rank(user_id=B, posts)
     ```

   - 截取前 N 筆（例如 20）：  
     ```
     topN = ranked_posts[0:N]
     ```

3. Feed Read Service 回傳 topN 貼文 + pagination cursor  
4. Client 顯示，並在使用者往下滑時使用 cursor 再拉下一批。

---

# 3. Component Deep Dive：Feed Fan-out Service

Feed Fan-out 是整個 pipeline 中最關鍵的 heavy lifting。

---

## 3.1 Fan-out 工作特點

- 每一篇貼文通常要 fan-out 給數十到數百 followers  
- 對「大 V」則可能是數百萬 followers  
- 發文峰值時間（晚上、活動期間）會放大寫入壓力  
- 但：  
  - 多數 followers 在短時間內不一定會打開 App  
  - 有些 followers 甚至是長期不活躍

---

## 3.2 實作策略

1. **普通帳號（小 to 中粉絲數）**
   - 完整 fan-out：  
     - 將 post_id 插入每個 follower 的 Feed Store inbox。  

2. **大 V / 名人帳號**
   - 使用 Hybrid 策略：  
     - 對「高活躍 followers」預先 fan-out（例如最近 7 天內有登入的）  
     - 其他 followers 在 read path 再從「作者時間線」直接抓帖子，做 lazy merge  
   - 優點：  
     - 降低超大 fan-out peak  
     - 保留熱門、活躍使用者的體驗

---

## 3.3 Feed Store 設計

Feed Store 通常會選擇：

- 使用 **NoSQL / KV + 排序**  
- 或 Redis / Aerospike 這類高效 in-memory 存儲，搭配持久化  

資料結構範例：

```
Key: user_id (feed owner)
Value: ordered list of (post_id, created_at, precomputed_score)
```

可用：

- Redis Sorted Set（score = time 或 pre_score）  
- 自訂 B+ tree / LSM-tree  

---

# 4. Component Deep Dive：Ranking Service

Ranking Service 是「把 candidate set 變成一個排序好的 feed」的關鍵。

---

## 4.1 Input / Output 介面

Input：

```
user_id
list of post candidates:
  - post_id
  - author_id
  - created_at
  - engagement_stats (likes, comments, etc.)
```

Output：

```
list of (post_id, score) sorted by score desc
```

---

## 4.2 特徵（Features）來源

1. **User features**
   - user 的興趣（追蹤誰、常按讚的主題、常看哪種內容）  
   - user 的裝置 / 地區 / 時區  

2. **Content features**
   - 貼文類型（photo / video / carousel）  
   - 主題（透過 hashtag / 影像理解模型）  
   - 貼文本身的「受歡迎程度」（likes, shares, comments, 保存數）

3. **User–Content interaction features**
   - user 過去與該作者互動頻率  
   - 是否曾收藏 / 分享該作者貼文  
   - 是否最近 mute / hide 過該作者

4. **Contextual Features**
   - 發文時間距離現在多久（recency）  
   - 使用者打開 App 的時間（早/午/晚）

---

## 4.3 Ranking pipeline

實際上 Ranking 可以分兩層：

1. **Pre-ranking / Filtering**
   - 把 feed inbox 裡的 1000 筆候選先篩到 200–300 筆  
   - 規則可能包括：
     - 太舊的貼文直接砍掉  
     - 過度重複的作者減少出現次數  

2. **Final ranking（ML model）**
   - 使用梯度提升樹 / DNN / 混合模型  
   - 計算每篇貼文被 user 互動的概率（例如 like、comment、long dwell）  
   - 根據預測的 engagement score 排序

---

# 5. Component Deep Dive：Social Graph Service

Social Graph Service 必須支援：

- 快速取得 user 的 followees / followers  
- 支持 bulk 查詢（一次查多個 user）  
- 支援更新（follow / unfollow）

---

## 5.1 資料模型

常見做法：  
用 KV 或 Sharded SQL：

```
Table: user_followees
  user_id
  followee_id
  created_at

Table: user_followers
  user_id
  follower_id
  created_at
```

或者只存一份 direction（followees），followers 用反向索引建出。

---

## 5.2 Cache

為了 Feed Fan-out 的效率，需要對：

- author 的 followers list 做 cache  
- 重點是減少對 graph store 的重複查詢

例如：

```
Cache Key: "followers:<author_id>"
Value: list of follower_ids
```

TTL 視情況設定（例如 5–30 分鐘），  
follow / unfollow 時可以標記 cache 失效（invalidation）。

---

# 6. Architecture Diagram（PlantUML，Hugo-safe）

以下是高階架構圖（針對 Home Feed 路徑）：

{{< plantuml >}}
@startuml
actor User as U

cloud "Instagram Backend" {
  [API Gateway]
  [Post Service]
  [Media Service]
  [Social Graph Service]
  [Feed Fan-out Service]
  [Feed Read Service]
  [Ranking Service]
  [Engagement Service]

  database "Post Store" as PostStore
  database "Media Blob Store" as MediaStore
  database "Social Graph Store" as GraphStore
  database "Feed Store (Inbox)" as FeedStore
  database "Engagement Store" as EngStore

  queue "Kafka / PubSub" as Kafka
}

U --> [API Gateway] : upload post / open app

[API Gateway] --> [Post Service] : publish post
[Post Service] --> PostStore
[Post Service] --> Kafka : post_created event

Kafka --> [Feed Fan-out Service]
[Feed Fan-out Service] --> [Social Graph Service]
[Social Graph Service] --> GraphStore
[Feed Fan-out Service] --> FeedStore : write to inbox

U --> [API Gateway] : open Home Feed
[API Gateway] --> [Feed Read Service]

[Feed Read Service] --> FeedStore : read inbox
[Feed Read Service] --> PostStore : batch get posts
[Feed Read Service] --> [Ranking Service] : rank(posts)
[Ranking Service] --> [Engagement Service] : (optional features/stats)
[Engagement Service] --> EngStore

[Feed Read Service] --> U : ranked feed

@enduml
{{< /plantuml >}}

---

## Fan-out Strategy + Feed Inbox + Caching + Home vs Explore  
# 1. Fan-out on Write vs Fan-out on Read vs Hybrid（深入版）

在 Part 1 我有提過三種模型，這裡會更深入分析：

- Fan-out on write（寫入時擴散）  
- Fan-out on read（讀取時聚合）  
- Hybrid（實務中 Instagram / Twitter 類似採用）

---

## 1.1 Fan-out on Write（寫時擴散）

流程概念：

1. 使用者 A 發文  
2. Feed Fan-out Service 讀取 A 的 followers：  
   ```
   followers = get_followers(author_id = A)
   ```
3. 對每個 follower f，把 post_id 寫入 f 的 feed inbox：  
   ```
   insert into FeedInbox (user_id = f, post_id, created_at)
   ```

### 優點：

- 讀取 feed 非常快：  
  打開 Home Feed 時，只要讀取自己的 FeedInbox 即可。  
- 簡化 Read Path：  
  不需要每次都去 query 多個作者的 timeline。

### 缺點：

- 對「粉絲極多的大 V / 名人」非常昂貴：  
  一篇貼文可能要 fan-out 給數千萬人。  
- 寫入放大（write amplification）：  
  ```
  一篇 post → N 筆 inbox 寫入
  ```
- Followers 中很多是不活躍使用者，會白白浪費 I/O 與儲存。

---

## 1.2 Fan-out on Read（讀時聚合）

流程概念：

1. 使用者 B 打開 Home Feed  
2. Feed Read Service：  
   - 查 B 追蹤的所有作者：  
     ```
     followees = get_followees(B)
     ```
   - 到每個 followee 的 timeline 去拿最近的 posts：  
     ```
     posts = union_of_recent_posts(followees)
     ```
   - 排序（按時間或 ranking score）

### 優點：

- 發文時幾乎只需寫一筆 Post，成本低。  
- 不受大 V 粉絲數影響，發文成本穩定。

### 缺點：

- 讀取成本極高：  
  如果 user B 追蹤 1000 個帳號，要從 1000 條 timeline 拿新貼文，做 sort & merge。  
- 很難在 P95 內壓低到 200ms 以內。  
- Cache 很難命中：每個人看到的組合都不同。

---

## 1.3 Hybrid Model（實務主流）

實際上的 Instagram / Twitter 類系統通常採：

- 對「普通使用者」使用 fan-out on write：  
  - followers 數量有限（幾百～幾千）  
  - 發文後 fan-out 是可以接受的。

- 對「大 V / 名人」採用 partial fan-out 或 pure fan-in：  
  - 對最近活躍的 followers 做 partial fan-out  
  - 其他 followers 在打開 feed 時再從「大 V 的作者 timeline」動態查詢

這樣可以兼顧：

- 普通用戶的 feed 讀取體驗（快）  
- 大 V 用戶的寫入成本（不被粉絲數炸掉）  
- 讀寫平衡（平衡 write 和 read 的資源消耗）

---

# 2. Feed Inbox 設計（Per-user Feed Store）

Feed Inbox 是 Hybrid 模式下的核心資料結構。

---

## 2.1 Feed Inbox 的資料模型

對每個 user，我們維護一個「已經為他 ready 好的候選貼文列表」。

範例結構：

```
Key: user_id (feed owner)
Value: ordered list of FeedEntry:
  FeedEntry = {
    post_id,
    author_id,
    inserted_at,
    pre_score (optional, e.g. time-decay based)
  }
```

可以用的底層技術：

- Redis Sorted Set  
- Aerospike / RocksDB（加上排序索引）  
- Sharded NoSQL（例如 Cassandra + clustering key）

---

## 2.2 Feed Inbox 寫入策略

當 Fan-out Service 處理 post_created 事件時：

1. 查 followers：  
   ```
   followers = get_followers(author_id)
   ```
2. 對每個 follower f 插入 FeedInbox：  
   ```
   zadd feed_inbox:f (score = created_at or pre_score, member = post_id)
   ```

可以對不同粉絲使用不同 score：

- 對高活躍 user，score 可以綜合  
  - 發文時間  
  - 與作者互動頻率  
- 對低活躍 user，只按時間即可

---

## 2.3 Feed Inbox 清理與過期（Eviction）

為了節省空間，不能永遠保留全部歷史：

- 可以只保留最近 N 天 / N 篇貼文。  
- 例如：  
  ```
  保留最近 1000 篇 candidate posts per user
  ```

當 inbox 超出上限時：

- 刪除最舊的 entries  
- 真正查歷史貼文時，可以 fallback 到「作者 timeline + Post Store」

---

# 3. Feed Caching（Hot / Warm / Cold）

Feed 讀取是最頻繁的操作之一，必須高度使用 cache。

---

## 3.1 層級化 Cache 概念

可分為：

1. **Hot cache（per user feed cache）**
   - 較短時間內頻繁打開 App 的使用者  
   - 將他的 topN feed 直接 cache 起來  

2. **Warm cache（partial feed / popular posts cache）**
   - 例如常出現在很多人 feed 裡的熱門貼文  
   - 可以在多個使用者間重複使用  

3. **Cold storage（Post Store / History DB）**
   - 不常被訪問的舊貼文  
   - 放在較便宜、延遲稍高的儲存系統

---

## 3.2 Home Feed Cache 策略

假設使用者 B 每天打開 IG 10 次：

- 第一次打開：  
  - 從 FeedInbox 讀取 candidates，送 Ranking Service，得到 topN  
  - 將結果存入 User Feed Cache：  
    ```
    cache_key = "home_feed:<user_id>:<bucket_id>"
    ```
- 後續短時間內的幾次打開：  
  - 可以先用 cache 結果，  
  - 背景再觸發增量更新（例如插入新貼文在前面）

優點：

- 大幅降低 Ranking Service QPS  
- 減少頻繁排序開銷

缺點：

- feed 稍微有「延遲感」（某些最新貼文會稍晚出現）  

所以常見作法：

- 每次打開 feed 時：  
  - 先回傳前面大部分來自 cache 的內容  
  - 再在最上面插入一些「最新的未 seen posts」  
  - 感覺起來 feed 既即時又流暢

---

# 4. Home Feed vs Explore Feed（差異與共用）

Explore Feed（推薦內容）和 Home Feed（追蹤內容）在架構上有共通點也有差異。

---

## 4.1 共用的部份

兩者都會使用：

- Ranking Service（或相似的 pipeline）  
- Post Store / Media Store  
- Engagement / Logging pipeline  
- Feature Store（模型特徵）

---

## 4.2 Home Feed 特性

- 來源主要是「使用者追蹤的人」  
- candidate set 通常較小（來自 user 的關係網）  
- 嚴重依賴 **Follow Graph + Fan-out Inbox**

---

## 4.3 Explore Feed 特性

- 來源是「全站或子集的熱門 / 相似內容」  
- candidate generation 來自：  
  - 相似度搜尋（embedding / ANN）  
  - global trending  
  - subscribed topics / hashtags  
- 需要一個 **Recommendation Candidate Generation Service**

簡化模型：

```
candidates = recsys.generate_candidates(user_id)
ranked = ranking_service.rank(user_id, candidates)
```

---

## 4.4 對系統設計的意涵

對於面試來說可以這樣總結：

- Home Feed：  
  - 重點在 **feed fan-out、inbox 設計、追蹤關係與排序結合**。  

- Explore Feed：  
  - 在 Home Feed 的 pipeline 上換掉「候選來源」，  
  - 候選生成由 **推薦系統** 來負責，  
  - 但最終的排序 / delivery / cache 可以共用同一套基礎設施。

---

# 5. Failure Scenarios 與一致性（Consistency in Feed）

---

## 5.1 發文已成功，但部分 followers 看不到？

原因可能是：

- Fan-out worker 部分失敗（例如一個 shard 掛掉）  
- FeedInbox 寫入失敗 / 延遲  
- Cache 未更新 / 落後

解決方法：

1. **重試機制（Retry / DLQ）**  
   - post_created 事件如果 fan-out 失敗 → 放入 Dead Letter Queue  
   - 由 background job 重試  

2. **Read Path 補救**  
   - 若 FeedInbox 遺漏某些 posts，  
   - 在 read path 過程中可從「作者 timeline」補抓缺漏  
   - 特別是對「關係緊密的作者」（例如常互動的朋友）

---

## 5.2 Feed 排序突然變得很奇怪（Model fail / 部署錯誤）

要有降級策略：

- Ranking Service 掛掉時：  
  - fallback 到 time-based 排序（by created_at）  
  - 或簡化 rule-based ranking  

這樣即使推薦品質下降，  
**至少系統仍然可用**（高可用性 > 排序完美）。

---

# 6. PlantUML：Fan-out + Feed Inbox + Ranking 流程圖

下面是本 Part 的核心流程圖，展示：

- 發文 → Fan-out → FeedInbox  
- 打開 App → FeedRead → Ranking → 顯示

{{< plantuml >}}
@startuml
actor Author as A
actor Viewer as V

A --> (Publish Post)
(Publish Post) --> [Post Service]
[Post Service] --> [Post Store]
[Post Service] --> (Emit post_created)

(Emit post_created) --> [Feed Fan-out Service]
[Feed Fan-out Service] --> [Social Graph Service] : get followers
[Social Graph Service] --> [Graph Store]
[Feed Fan-out Service] --> [Feed Store] : insert post_id into followers' inbox

<!-- == Viewer reads feed == -->

V --> (Open Home Feed)
(Open Home Feed) --> [Feed Read Service]
[Feed Read Service] --> [Feed Store] : read inbox (candidates)
[Feed Read Service] --> [Post Store] : batch load posts
[Feed Read Service] --> [Ranking Service] : rank(user, posts)
[Ranking Service] --> [Engagement Service] : (optional features)
[Engagement Service] --> [Engagement Store]

[Feed Read Service] --> V : ranked feed

@enduml
{{< /plantuml >}}

---

## Scalability, Sharding, Multi-region, Performance Engineering  


# 1. Scaling Goals（整體擴展目標）

Instagram feed 系統的主要挑戰：

1. 數十億貼文與數億 DAU  
2. Feed Read QPS 可達數十萬甚至百萬級  
3. 發文峰值時 Fan-out 會引發寫入風暴  
4. 多地區（multi-region）需要低延遲存取  
5. 大量圖片 / 影片需透過 CDN 快速交付  

本 Part 專注於：

- Sharding（作者 / 使用者 / 地區）  
- 全球多資料中心部署（Multi-region Active-active）  
- Feed pipeline 的延遲優化  
- Cache 分層（multi-layer caching）  
- Storage tiering（Hot/Warm/Cold）  

---

# 2. Sharding Strategy（分片策略）

Instagram 規模下，單一資料庫一定撐不住，需要分片 + 多層儲存。

---

# 2.1 Post Store Sharding（按作者分片）

貼文基本上是：

```
Author-centric → 一個作者的貼文全部存在同一 shard
```

理由：

- 大部分讀取都是「批次查詢某作者的貼文」  
- 排序依時間 → append-friendly  
- 作者的寫入負載天然地平均分散（global users）  

分片鍵：

```
shard_id = hash(author_id) % N
```

這讓每個作者的 timeline 落在確定 shard。

---

# 2.2 Feed Inbox Sharding（按收件者 user_id 分片）

FeedInbox（per-user feed list）通常以：

```
shard = hash(user_id) % N
```

理由：

- Feed read 是以 user 為單位  
- Read Path 高 QPS → 分片可水平擴展  
- inbox 寫入（fan-out）雖然多，但分片後可分散到許多 worker

---

# 2.3 Social Graph Sharding

Graph Store 可以採：

1. **user_id-based sharding**  
2. **雙向列表分離（followees, followers）**

例如：

- followees: user_id → list of followees  
- followers: user_id → list of followers  

巨大帳號（大 V）要特別處理：

- followers 清單很大 → 分 bucket 儲存  
- 不用一次載入所有 followers，只需要活躍 subset

---

# 2.4 Global Sharding（地區分片）

以地區劃分資料中心：

- US-East  
- US-West  
- Europe  
- Asia-Pacific  

User region 由：

```
home_region = hash(user_id) % RegionCount
```

或由：

- 註冊地  
- 使用頻率最高地  
- GeoIP  

FeedInbox 與 Posting 會綁定到使用者的「home region」。

---

# 3. Multi-region Architecture

Instagram 屬於「全球高延遲敏感服務」，解決方式：

---

# 3.1 Multi-region Active-active（前端）

API Gateway / Feed Read Service / Post Service 通常做：

- Active-active  
- User 來自哪個地區就打最近的 region  
- 所有 region 互相備援

---

# 3.2 Storage Tier 的 Global Strategy

### Post Store（metadata）
常用 eventually consistent / leaderless NoSQL（例如 Cassandra、Dynamo-style）：

- 多副本跨 region  
- 用 Quorum / LOCAL_QUORUM 讀寫  

### Media Store（圖片 / 影片）
- S3 多地區複製  
- 配合 CDN edge caching

### Feed Inbox Store（region-local）
Inbox 通常 **不跨 region**。

原因：

- inbox 是 per-user 的 cache-like structure  
- 如果 user 永遠在 APAC，沒必要讓 inbox 存在美國  
- 反而 cross-DC replication 會增加延遲與成本

規則：

```
FeedInbox 存在 user 的 home region，不需要 global replication
```

---

# 3.3 Cross-region Consistency Issue

若作者與讀者不在同一 region？

流程如下：

1. 作者 A 在 US-East 發文  
2. post_created event 複製（multi-region Kafka / log replication）  
3. APAC region 的 fan-out worker 會消費到這個事件  
4. 插入 APAC region 當地的 follower inbox

→ feed delivery 可能有 **1–5 秒跨區延遲**，但可接受。

---

# 4. Performance：降低 Read Path 延遲

Feed Read 是最核心的高 QPS 流程，需極度優化。

---

# 4.1 Multi-stage Caching

為了在 200ms 內回應 feed，需要以下 cache：

### 1. Per-user Feed Cache（Hot）
- cache top N（例如前 20 篇）  
- hit rate 可達 60–90%

### 2. Post Metadata Cache（Warm）
- 不要每次都 query Post Store  
- 批次讀取後會快取 metadata（caption / media refs）

### 3. User Feature Cache（for ranking）
- 排序模型需要 user 特徵 → 預先 cache

### 4. Content Feature Cache（for ranking）
- 特徵工程（embedding, topic）可能耗時

---

# 4.2 Batch operations（批處理優化）

Read path 一定要 **減少 round trips**：

- 批量讀取 Metadata：  
  ```
  batch_get_posts([post_ids])
  ```

- 批量讀取作者資訊：  
  ```
  batch_get_users([author_ids])
  ```

- 批量 Ranking：  
  ```
  ranking_service.rank(user_id, candidate_posts)
  ```

Ranking Service 通常使用：

- gRPC（低延遲 / 多路複用）  
- Keep-alive connections  
- Async I/O  

---

# 4.3 Ranking latency 優化

Ranking pipeline 可分 3 層：

1. **Pre-ranking：過濾 2000 → 300 篇**（rule-based）  
2. **Lightweight Model ranking：300 → 100**（快速模型）  
3. **Heavy Model ranking：100 → 20**（精準但較慢）

重點：

- 每一層都做 batch  
- 增量更新（只重新算新的貼文，不全量更新）  
- 避免每次讀取 full embeddings / heavy features

---

# 5. Storage Tiering（冷熱資料分層）

Instagram 需要存數十億貼文，但不是每篇都需要同樣的速度。

---

# 5.1 Hot Storage（短期高頻）

例如：

- 最新 1–3 天貼文  
- 存在 NoSQL / Redis（高 QPS、高 IPC、低延遲）  
- 排序、探索、推薦都常用到

---

# 5.2 Warm Storage（低頻訪問）

例如：

- 1 週以上的貼文  
- 存於 Cassandra / Bigtable  
- feed inbox 通常會只引用 post_id，metadata 從 warm storage 取

---

# 5.3 Cold Storage（歸檔）

例如：

- 1 年以上貼文  
- 儲存在 S3 / HDFS  
- 通常出現在 hashtag 搜尋或 profile 過往瀏覽

---

# 6. Scalability：Handling Peaks（事件高峰處理）

Instagram 會遇到極端峰值，例如：

- 大明星發文  
- 全球事件（體育、選舉）  
- 新功能上線  
- 跨年、節慶時間

問題：Fan-out / Ranking QPS 大幅飆高。

---

# 6.1 策略 1：大 V 特殊處理

大 V（例如 10M 粉絲）貼文不做 full fan-out：

- 只 fan-out 給最近活躍的 1–5% followers  
- 其他 followers 用 read-time fetch（lazy fan-in）

---

# 6.2 策略 2：FeedInbox Soft-limit

每個 user 的 inbox 分頁可限制：

```
max_inbox_size = 1000 (keep last 1000 posts)
```

避免 inbox script 過大，讀取過慢。

---

# 6.3 策略 3：Backpressure + DLQ

若 Kafka fan-out 壓力過高：

- worker 調整消費速率  
- 將落後事件放入 DLQ  
- background job 緩慢補寫 inbox  
- 用 read-path fallback 補漏

---

# 7. Instagram Multi-region Architecture Diagram（PlantUML）

以下示意 Home Feed 在多地區如何協作：

{{< plantuml >}}
@startuml
rectangle "US-East Region" {
  [API Gateway US]
  [Post Service US]
  [Feed Fan-out US]
  [Feed Read US]
  database "Post Store US"
  database "FeedInbox US"
  queue "Kafka US"
}

rectangle "EU-West Region" {
  [API Gateway EU]
  [Post Service EU]
  [Feed Fan-out EU]
  [Feed Read EU]
  database "Post Store EU"
  database "FeedInbox EU"
  queue "Kafka EU"
}

rectangle "APAC Region" {
  [API Gateway APAC]
  [Post Service APAC]
  [Feed Fan-out APAC]
  [Feed Read APAC]
  database "Post Store APAC"
  database "FeedInbox APAC"
  queue "Kafka APAC"
}

[Post Service US] --> "Kafka US" : post_created
"Kafka US" --> [Feed Fan-out US]


"Kafka US" <--> "Kafka EU"
"Kafka US" <--> "Kafka APAC"

[Feed Fan-out APAC] --> "FeedInbox APAC"
[Feed Fan-out EU] --> "FeedInbox EU"

@enduml
{{< /plantuml >}}

---

# ✔️ Part 4 完成（可直接存成 instagram_part4_scalability.md）

你現在擁有：

- Sharding（作者 / 使用者 / 地區）  
- Multi-region Active-active 架構  
- Cache / Storage tiering  
- Ranking latency optimization  
- Peak load mitigation  
- PlantUML 圖示  
---
## Follow-up Questions + Deep Answers（Feed / Fan-out / Ranking）  

# 1. Fan-out on Write vs Read：如果粉絲數巨大怎麼辦？

### 問題：
作者是大 V（例如擁有 10M followers），fan-out on write 會造成寫入風暴。

### 理想回答：
採用 **Hybrid Model**：

1. 只對最近活躍 followers（例如過去 7 days active）做 fan-out  
2. 對 inactive followers 採用 **read-time aggregation**  

如此可避免大規模寫入壓力，同時保持 feed 體驗。

---

# 2. Feed Inbox 是 cache 還是 source of truth？

Feed Inbox 並非唯一真相（source of truth），而是：

```
A high-performance, user-centric, precomputed candidate list
```

真正的 source of truth 是：

- Post Store（貼文 metadata）  
- Engagement Store  
- Graph Store  

FeedInbox 可以刪除、重建、過期（TTL），不會造成資料不一致。

---

# 3. FeedInbox 如何避免無限制增長？

三種策略：

1. 保留最近 N 筆（例如 1000）  
2. 設定 TTL（例如保留 7–14 天）  
3. 定期 GC（後台批次清理）

FeedInbox 像是「使用者可能會看的候選貼文」，與實際貼文歷史不同。

---

# 4. Ranking latency 過高怎麼辦？

常見的優化：

- multi-stage ranking（filter → light → heavy）  
- batch ranking  
- feature caching  
- incremental ranking（只重新排序新進入 feed 的貼文）  
- GPU inference（如 Reels / Video ranking）

---

# 5. 使用者追蹤 3000 個人，如何避免 read bottleneck？

FeedInbox 的核心目的就是：

```
避免在 read path 去查 3000 個作者的時間線
```

做法：

- write-time fan-out 讓 read 避免聚合多個作者 timeline  
- large follow graph 仍然有 partial fan-in，但範圍有限

---

# 6. FeedInbox 與作者 timeline 有什麼差別？

| 類別 | 說明 |
|------|------|
| 作者 timeline | 作者自己的時間序（按發文時間排列） |
| Feed Inbox | 使用者看到的候選貼文列表（per user） |

FeedInbox 可能包含：

- 不同作者  
- 依不同 score 排列  
- 已經過濾的貼文（隱藏 / mute / blocked）

---

# 7. FeedInbox 會不會因為 ranking 太慢而卡住？

解法：**延後排序（lazy ranking）**

流程：

1. Fan-out 寫入 inbox 時只寫入 post_id + timestamp  
2. Ranking 在 read-time 才做  
3. 或 pre-rank（輕量 score）後 read-time fine tuning  

這樣可以保持 write path 非常輕量。

---

# 8. 如果使用者瞬間新增 2000 個 followees 會發生什麼？

FeedInbox 會「增量更新」：

- 不會一次 fan-out 所有 followees 的過往貼文  
- 只會加入新 followees 未來的貼文  
- 過往貼文將由 read-time fetch 決定是否需要加入 feed  

好處：

- 避免一次性灌入大量 post_id  
- UI 可以用「某某人開始追蹤某某」方式自然引導

---

# 9. 如何避免一個作者的貼文霸佔 feed？

Ranking feature：

- 作者多樣性（author diversity）  
- 對重複作者做 diminishing return  
- 根據使用者偏好控制多樣性程度

Ranking model 會避免：

- 某作者連續出現 5–10 篇

---

# 10. 如何控制 feed 新鮮度（freshness）？

Ranking 會加入：

- freshness score  
- 時間衰減（time decay）  
- breaking news / hot content 提升權重  

或採：

```
final_score = α * relevance + β * recency
```

---

# 11. 如何避免 feed 出現老貼文？

由 feed inbox eviction 控制：

- 每人最多保留 1000 筆  
- 超過就丟掉最舊的  

Ranking 也會加入 timestamp penalty。

---

# 12. 如果作者刪除貼文怎麼同步更新 feed？

流程：

1. PostService 發布事件：post_deleted  
2. FeedInbox Worker 消費事件，刪除該 post_id  
3. FeedReadService 遇到已刪除的 post_id → skip or re-fill  

---

# 13. 如何防止違規貼文已被刪除但仍出現在部分 feed？

可以做：

1. **central blocklist**（全域貼文黑名單）  
2. feed read 階段做 content validity check  
3. strong TTL（feed inbox 不保留過久）  
4. ranking 服務避免回傳被封鎖內容  

---

# 14. 如何做 Home Feed 與 Explore Feed 的融合？

方法：

- Home 在前 1–2 slots  
- Explore 或推薦在後面 slots  
- ranking model 支援跨來源 candidate  

---

# 15. 如果 FeedInbox 存在不同 region 怎麼同步？

答法：

- FeedInbox 是 region-local，不做跨區同步  
- 貼文事件是 global replicated  
- 每個 region 自己 fan-out 給自己 region 的 followers  

這樣才能：

- 避免跨區寫入負擔  
- 減少延遲  
- 保持多 region 故障隔離

---

# 16. 當 ranking model 版本切換時如何避免 feed 混亂？

使用 A/B bucket：

- user_id % 100 → bucket  
- bucket 決定 ranking 模型版本  
- 確保同一 user 在 session 內保持一致的 ranking 行為

---

# 17. 如何讓 feed 個人化（personalized）？

Ranking 會依以下特徵個人化：

- user 行為（like, dwell time, skip）  
- 興趣 embedding  
- 與作者互動頻率  
- 過往瀏覽與停留模式  
- 時段偏好  

---

# 18. 如何減少 Ranking 對記憶體 / CPU 需求？

技術：

- feature pre-computation  
- feature caching  
- quantization（向量壓縮）  
- 部署模型至 GPU pool  
- lazy loading（按需取特徵）

---

# 19. 如何保證 feed 不會重複顯示同貼文？

做法：

- feedInbox 本身不會重複插入同 post_id  
- ranking service 去重（dedupe）  
- client 也可做 seen-set 管控

---

# 20. PlantUML：Feed Follow-up Summary

{{< plantuml >}}
@startuml
actor User

rectangle "Read Path" {
  User --> (Open Feed)
  (Open Feed) --> [FeedReadService]
  [FeedReadService] --> [FeedInbox]
  [FeedReadService] --> [PostStore]
  [FeedReadService] --> [RankingService]
  [RankingService] --> [FeatureStore]
  [FeedReadService] --> User : ranked feed
}

rectangle "Write Path" {
  (Publish Post) --> [PostService]
  [PostService] --> [PostStore]
  [PostService] --> (post_created)
  (post_created) --> [FanOutWorker]
  [FanOutWorker] --> [FeedInbox]
}

@enduml
{{< /plantuml >}}

# 21. 如果 Post Store 用 NoSQL（例如 Cassandra），如何避免 partition hotspots？

問題場景：

- 某些作者粉絲很多 → 貼文特別多  
- 若 partition key 選擇不當可能造成 write hotspot  

### 解法：

依 **author_id** sharding：

```
partition_key = hash(author_id)
```

優點：

- 採 hash 分散，避免某作者寫入落在同一節點  
- Metadata append-friendly（按時間排序）  

也可以加入 clustering key：

```
(author_id, created_at desc)
```

改善 scan 行為。

---

# 22. FeedInbox 存在什麼 storage？為何不使用 SQL？

FeedInbox 有以下特性：

- 每個 user 會有數百到上千筆候選  
- 插入極多（fan-out）  
- 讀取極高 QPS（feed read）  
- 不需要強一致  

這些都很適合：

- Redis Sorted Set  
- Aerospike  
- Cassandra + clustering key  
- RocksDB（LSM-based）

不用 SQL 的原因：

- transactional cost 高  
- join / foreign keys 無意義  
- 寫入風暴時容易造成 lock contention

---

# 23. FeedInbox 是否要持久化？還是只放記憶體？

最佳實務：

- 使用 Redis **或** memory-first 實作  
- **但仍有持久化**（AOF / snapshot / RocksDB）  

原因：

FeedInbox 像「每個 user 的動態候選」，不是 source of truth。  
但：

- 重建成本巨大（每次都要重新跑 fan-out）  
- 重建會影響 feed 延遲  

所以需要：

```
memory store + persistent snapshot
```

---

# 24. 多 Region 架構：FeedInbox 需要跨區同步嗎？

**不需要。**

理由：

- FeedInbox 是「per-user」結構  
- 每個 user 只會在自己所在的 home region 使用 feed  

只需要：

- 將作者貼文事件（post_created）跨區複製  
- 各區 fan-out 自己執行

好處：

- 避免跨 DC traffic  
- 保持低延遲  
- 符合每地區的 data locality

---

# 25. 若 region 失效，使用者如何 failover 到其他地區？

步驟：

1. 由 DNS / global traffic manager 將流量導向其他 region  
2. 在 failover region：  
   - PostStore 有 global replicated data  
   - GraphStore 也有 multi-region replicas  
3. FeedInbox 在 local region 不存在 → 重建  
   - 回到 read-time fetch（fallback mode）  
   - 之後由 Fan-out worker 重建 inbox  
   - 可能導致 feed 略有延遲，但不會停擺

---

# 26. 如何分片 Social Graph（followers/followees）？

常見設計：

```
shard_key = hash(user_id)
```

每個 user 的 followers/followees 列表切在不同 shard。

對大 V，要支援：

- 分 bucket 儲存（例如 followers:0-1M 存 bucket_1，1M-2M 存 bucket_2）  
- 批次載入避免超大列表卡死

---

# 27. 大 V 的 followers 數量過大，Fan-out 必須做哪些優化？

### 核心方法：

1. 活躍 subset fan-out  
2. 其他 followers 改成 read-time merge（fan-in）  
3. 追蹤者依活躍程度排序（LRU）  
4. 批次 fan-out（micro-batching）

### 優化邏輯：

```
if follower.isActiveRecently():
    fanOut(follower)
else:
    skip
```

---

# 28. 當 Graph Store 到達數十億關係時，如何避免 query latency 過高？

策略：

1. followers list 分頁  
2. followers 依活躍度排序  
3. 使用 bloom filter 檢查關係存在性  
4. caching（key: followers:<user_id>）  
5. time-based window（只查最近活躍 followers）

---

# 29. 為什麼推薦使用 Kafka 做事件傳遞（post_created）？

因為 Kafka 的特性：

- 高吞吐（寫入上百 MB/s）  
- 可水平擴展 partitions  
- 保證 order（同一作者的貼文）  
- 支援 consumer groups（fan-out workers 可水平擴展）  
- failover / replay 能力強

對於 Instagram feed：

- fan-out 寫入量非常大  
- 每次巨量發文事件可以被 workers 分散處理  
- 能應付 peak load（例如明星 IG live 完發文）

---

# 30. Post Store 分片後如何做全站熱門（global trending）？

需要一個額外的 Aggregator Service：

- 從 engagement logs（likes/comments/shares）彙整資料  
- 不依賴單一 region 的 PostStore  
- 全站熱門藉由 logs 而不是讀 storage

---

# 31. Multi-region replication 如何降低寫入衝擊？

兩種策略：

1. **Async cross-region replication**  
   - 貼文寫入先在本 region 成功  
   - 之後由 log replicator 傳播到其他 region  

2. **Local quorum writes**  
   - Cassandra LOCAL_QUORUM  
   - 速度快、延遲低

用於 feed 的資料通常採 eventual consistency。

---

# 32. FeedInbox 很大時如何提升讀取速度？

提升方式：

1. Inbox 分段存放（split into segments）  
2. 將 inbox entry 存成輕量結構（post_id + timestamp）  
3. 前 X 項常駐記憶體 cache  
4. 背景清理老舊 entries  

Inbox 絕不能：

- 存太多 metadata（增加 payload 大小）  
- 調太大（例如 > 10k entries）  

通常控制在：

```
max_inbox_size = 500 ~ 2000
```

---

# 33. 如果 Ranking Service 掛了，FeedRead 是否要等？

不能等。

降級策略（Graceful Degradation）：

1. fallback to time-order ranking  
2. 最近互動作者優先（簡單 rule-based）  
3. return partial ranking（例如只排前 50 筆）  

高可用性優先於高品質 feed 排序。

---

# 34. 多 Region 間 clock skew（時鐘不同步）會造成什麼問題？

若直接用 timestamp ranking：

- 貼文可能跨區排序錯誤  

解決方法：

1. 使用 Lamport clock 或 Hybrid Logical Clock（HLC）  
2. 最終 ranking 加 recency window，允許偏差 ±60s  
3. 使用 server-side timestamp 而非 client timestamp

---

# 35. 多 Region 讀寫不一致如何影響 feed？

如果 APAC region 比 US region 落後：

- 使用者會看到較舊的內容（bounded staleness）  

可接受，因為：

- feed 本質上是 eventual-consistent  
- 排序結合 recency 可減少影響  

---

# 36. 若整個 Region 掛掉，多 Region 架構如何自我修復？

步驟：

1. redirect traffic 至 nearest region  
2. 權重調整（geo load balancing）  
3. FeedInbox fallback → read-time fetch  
4. Replicated PostStore & GraphStore 自動接管  
5. Region 恢復後重建 FeedInbox  

---

# 37. 為什麼 FeedInbox 最適合 local-region only？

因為：

1. inbox 是高 QPS 快取，不該跨 DC  
2. 不同 region 間 latency 高（>100ms）  
3. 跨 DC 寫入成本極高  
4. 失效時可 fallback，因此不需要一致性 replication  

Inbox 不是永久資料，不需要 global correctness。

---

# 38. social graph 更新（follow/unfollow）如何同步 feed？

處理方式：

1. follow(event)：  
   - 將新 followee 之後的貼文加入 inbox（非歷史貼文）  

2. unfollow(event)：  
   - 在 inbox 中移除該作者未讀內容  
   - 或 read-time skip  

保持操作輕量。

---

# 39. 多 Region ML Ranking 如何同步模型？

模型同步方式：

- 模型檔案存 S3（versioned）  
- region workers 啟動時從 central storage 拉取  
- 透過 feature store 同步 features  
- A/B bucket 決定模型版本使用者群

---

# 40. PlantUML：Multi-region Sharding Summary

{{< plantuml >}}
@startuml

cloud "US-East" {
  database "PostStore-US"
  database "GraphStore-US"
  database "FeedInbox-US"
  queue "Kafka-US"
  [FanOut-US]
}

cloud "EU-West" {
  database "PostStore-EU"
  database "GraphStore-EU"
  database "FeedInbox-EU"
  queue "Kafka-EU"
  [FanOut-EU]
}

cloud "APAC" {
  database "PostStore-APAC"
  database "GraphStore-APAC"
  database "FeedInbox-APAC"
  queue "Kafka-APAC"
  [FanOut-APAC]
}

[ Kafka-US ] <--> [ Kafka-EU ]
[ Kafka-US ] <--> [ Kafka-APAC ]

@enduml
{{< /plantuml >}}

# 41. 如果 FeedInbox 遺漏了一些貼文怎麼辦？（Missing posts）

### 問題來源：
- Fan-out worker 落後  
- Kafka 消費者重啟  
- Region failover 造成部分事件未被寫入 inbox  

### 解法：

1. **Read-path recovery（最重要）**  
   FeedReadService 可以檢查：  
   若某作者最近有新貼文，但 inbox 沒有 → 自動補抓：

   ```
   posts = fetch_recent_posts(author_id, window=24h)
   ```

   合併後再 ranking。

2. **Kafka replay**  
   對落後分區做 replay，補齊 fan-out。

3. **Dead Letter Queue（DLQ）復原**  
   失敗事件不丟棄，定期重新處理。

---

# 42. 當 Kafka backlog 過大，Fan-out 會延遲多久？怎麼避免？

### 原因：
- 突然大量貼文（大 V 發文）  
- 大量 users 同時上線  
- Workers 無法即時消費 Kafka topic

### 防禦策略：

1. **Auto-scaling fan-out workers**  
2. **Limit fan-out per user（大 V 部分 fan-out）**  
3. **Prioritize active followers**  
4. **Backpressure control（調整 fetch size）**

---

# 43. 如果 Ranking Service latency 飆高而造成 Feed timeout？

不能讓使用者看到 loading spinner 卡死。

### 解法：

1. **Fallback ranking：**  
   ```
   final = sort_by_timestamp(candidates)
   ```

2. **Delivery partial results：**  
   - 若 ranking 只完成 80%，先回傳已有的 sorted 部分。

3. **Timeout budget（例如 30ms / model）**  
   過時即 fallback。

---

# 44. 如何避免 FeedReadService 的 N+1 查詢問題？

要做 **批處理**：

- batch_get_posts(post_ids)  
- batch_get_authors(author_ids)  
- batch_ranking(candidates)

所有 dependent services 都必須支援批量 API。

---

# 45. 如果 PostStore metadata 與 MediaStore（圖片）不同步？

例如：

- metadata 寫入成功  
- 圖片上傳到 S3 失敗  

### 解法：

1. PostService 使用兩階段 commit：  
   - metadata tentative store → media upload → metadata finalize  

2. 若 media upload 失敗：  
   - 發布補救事件  
   - 清除未完成貼文  
   - 不觸發 fan-out

---

# 46. 如何讓 feed 在弱網路環境也能運作？

1. 回傳較低解析度的圖片 URL  
2. 使用 CDN edge compression  
3. Client 預抓上一頁與下一頁  
4. 客戶端可採 incremental rendering：  
   - metadata 先顯示  
   - 圖片 deferred load

---

# 47. 使用者被封鎖（Block）後如何保證看不到對方貼文？

FeedInbox 不能完全依賴。

### 解法：

1. Ranking 時過濾 blocked authors：  
   ```
   if author in user.blocked_list: skip
   ```

2. FeedReadService 將 inbox entries 做 filter  
3. Explore Feed 也使用 blocklist

Block 必須是 **server-side enforcement**，不能交給 client。

---

# 48. Explore Feed 的延遲如何控制在 300ms 內？

Explore pipeline 雖然費時，但透過：

1. **candidate generation caching**  
2. **embedding ANN search（向量近似查詢）**  
3. **GPU-based ranking**  
4. **multi-stage ranking（提前過濾）**

可以將候選數量縮小到 manageable level。

---

# 49. 如何避免貼文被「洗掉」（大量其他人發文造成 inbox overflow）？

策略：

1. inbox 動態調整大小（1000 → 1500）  
2. 將 high affinity 內容固定在 inbox 前方（pinned slots）  
3. 對重要作者設置優先級（優先寫入 inbox）  

---

# 50. 系統如何避免 feed 陷入“echo chamber”（迴音室）？

Ranking 模型加入：

- author diversity  
- content diversity  
- topic exploration（少量探索內容）

有助於增加內容多樣性。

---

# 51. 如何偵測 feed 質量惡化？

透過 signals：

- dwell time 下降  
- likes / comments per impression 下降  
- negative feedback（hide / report）增加  
- users 打開 app 的頻率下降  

利用 analytics pipeline 每分鐘更新問題指標。

---

# 52. 當 PostStore 某 shard 掛掉會怎麼影響？

行為：

- FeedInbox 仍然有 post_id  
- 但 FeedReadService 讀 metadata 會失敗  

處理：

- 讀取 fallback（跳過此 post）  
- 顯示 placeholder  
- background job 修復（restore from replicas）  

可用 Cassandra / Bigtable 等底層具備 multi-replica 修復。

---

# 53. 如何提升 PostStore 的讀取 QPS？

方法：

1. metadata cache（Memcached / Redis）  
2. 把 caption / hashtags 等次要字段拆出（field-level split）  
3. 使用 column-oriented NoSQL  
4. 增加 shard 數量  
5. enable row cache（如 Cassandra row cache）

---

# 54. 如何讓多 region Edge API 決定 routing？

通常用：

- Global Load Balancer（Geolocation routing）  
- DNS with latency-based routing  
- Edge POPs（Cloudflare / AWS Global Accelerator）

機制：

```
client → nearest POP → nearest health region
```

---

# 55. 如何量化 Feed 系統的效能 SLA？

分成：

### 1. Latency SLA  
- P95 feed read < 200ms  
- P95 ranking < 50ms  
- P99 fan-out < 10 seconds

### 2. Availability SLA  
- feed read 99.9%  
- ranking degraded but available 99.99%

### 3. Freshness  
- new posts seen by majority of followers < 5 seconds

---

# 56. 如何衡量系統是否需要增加 shards？

要監控：

- shard CPU / memory usage  
- fan-out backlog  
- inbox size growth  
- PostStore partition size  
- P99 read latency

若超過閾值，做：

- re-sharding  
- consistent hashing  
- 增加 shards（Cassandra add nodes）

---

# 57. 如何減少跨節點（cross-shard）讀取？

策略：

1. sharding 按 user_id 或 author_id 保證 locality  
2. feed read 不依賴多作者 timeline（因為 inbox 已合併）  
3. 批處理 reduce calls  
4. 多層快取降低後端 hits

---

# 58. FeedInbox 與 Ranking 結合時如何避免 ranking bottleneck？

技術：

1. pre-ranking score  
2. 只 rank top-K candidates  
3. 分批 ranking  
4. 多模型管線（light model → heavy model）  
5. 增量 ranking（只重排新進貼文）

---

# 59. 重發貼文（repost）如何處理？

可當作新 event：

1. fan-out 重新寫入受眾的 inbox  
2. ranking 特徵中加入 repost factor（但不應過度提升排名）  
3. inbox dedupe 避免重複顯示

---

# 60. Feed 為何必須是 eventual consistency？不能強一致嗎？

原因：

1. feed 是給使用者「瀏覽」用，不需要交易級一致性  
2. ranking 本身就非確定性  
3. 多 region 寫入無法做到 global strong consistency  
4. 使用者不會感知到 5–10 秒的貼文延遲  

強一致會讓：

- latency 上升  
- 系統負擔增加  
- multi-region 變得複雜

---

# 61. 系統如何防止 Spam Account 掃掉 feed 內容？

透過 spam detection：

- account reputation score  
- abnormal activity detection（like burst, posting burst）  
- engagement anomalies  
- IP / device fingerprint  
- ranking penalty  

---

# 62. 如何避免 engagement signal 被濫用？

演算法加入：

- weighted interactions（like < comment < share < save）  
- downweight 最短 dwell time  
- 過度快速點讚 → 降低權重  

---

# 63. 若 Ranking Service 需重訓模型，如何不中斷服務？

技術：

1. model versioning  
2. canary deployment  
3. A/B bucket rollout  
4. rollback safety  

即使 ML pipeline 更新，feed 仍能以舊模型服務。

---

# 64. FeedInbox 如果突然暴增（e.g., spam attack）如何處理？

方法：

1. rate limit per author  
2. spam filter before fan-out  
3. follower segmentation（給不同 bucket 不同速率）  
4. inbox soft-cap（不超過 1500 entries）

---

# 65. 遇到突發大量機器人帳號（bot）怎麼辦？

處理：

- 預先檢測 fake graph  
- 加強 follow request validation  
- 新帳號限速（posting / following）  
- suspicious content 不做 fan-out

---

# 66. PlantUML：Failure Handling & Fallback Overview

{{< plantuml >}}
@startuml

actor User

rectangle "Feed System" {
  [FeedRead] --> [Ranking]
  [Ranking] --> [FeatureStore]

  [FeedRead] --> [PostStore] : fallback if inbox missing
  [FeedRead] --> [GraphStore] : re-validate author relationship

  [FanOut] --> [FeedInbox]
  [FanOut] --> [DLQ] : errors

  [DLQ] --> [RecoveryJob]
}

User --> [FeedRead] : open app
[FeedRead] --> User : feed (fallback if needed)

@enduml
{{< /plantuml >}}

---

## 4. News Feed（Facebook / Instagram 類）

### 4.1 題目重述與假設

- 題目：設計一個社群平台的 News Feed 系統。  
- 功能需求：  
  - 使用者看到「自己關注的人 / page」的貼文 feed  
  - 支援時間排序 / 相關度排序  
  - 支援無限捲動（pagination / cursor）  
- 非功能需求：  
  - Read-heavy、高 QPS  
  - Feed latency 可接受 1–10 秒延遲  
  - 要支援 ranking 演算法演進  

### 4.2 高階架構說明

- Fan-out on write / on read 混合：  
  - 高度活躍使用者：on read 從 Post Store + Social Graph 動態組裝。  
  - 一般使用者：維護 precomputed feed timeline（cache / DB）。  
- Ranking service：  
  - 依據文本、互動（likes/comments）、社交距離、時間 decay 等信號計算 score。  

### 4.3 PlantUML

{{< plantuml >}}
@startuml
title News Feed - High Level Architecture

actor User
rectangle "Mobile / Web App" as CLIENT
rectangle "Feed API Service" as FEEDAPI

rectangle "Social Graph Service" as GRAPH
database "Graph DB (follows)" as GRAPHDB

rectangle "Post Service" as POST
database "Post Store" as POSTDB

rectangle "Feed Fanout Service" as FANOUT
database "User Feed Store (precomputed timelines)" as FEEDDB

rectangle "Ranking Service" as RANK
database "Engagement Store" as ENGDB

User --> CLIENT : open app
CLIENT --> FEEDAPI : get /feed

FEEDAPI --> FEEDDB : get precomputed feed
FEEDDB --> FEEDAPI : candidate posts
FEEDAPI --> RANK : rank candidates
RANK --> ENGDB : fetch engagement signals
RANK --> FEEDAPI : ranked posts
FEEDAPI --> CLIENT : personalized feed

' Publishing flow
CLIENT --> POST : create post
POST --> POSTDB : store post
POST --> GRAPH : get followers
GRAPH --> GRAPHDB
POST --> FANOUT : fan-out post to followers
FANOUT --> FEEDDB : append to user timelines

@enduml
{{< /plantuml >}}

### 4.4 口頭講稿（約 2–3 分鐘）

> Feed 系統的關鍵在於 fan-out 策略和 ranking。  
> <br>
> 對於一般使用者，我會採用「fan-out on write」：當某人發文時，系統會查出他的 followers，然後把這篇貼文的 ID append 到 followers 的 feed timeline 存在 User Feed Store 中。之後讀 feed 時就只是從自己的 feed list 取出一批 candidate，再交給 Ranking Service 排序。  
> <br>
> 對於有超大量 followers 的大 V，我可以改成部分 fan-out on read：讀取時動態從 Post Store + Graph 取資料，避免寫入爆炸。  
> <br>
> Ranking Service 會根據文本、互動行為、社交距離與貼文新舊做 scoring。整個系統可以透過 cache、sharding 以及異步 fan-out 來 scale。  

---