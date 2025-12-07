---
date: '2025-12-07T17:36:48+08:00'
draft: false
categories:
    - performance
    - cache
    - database
title: 系統設計：緩存策略完整指南 (Cache Patterns Guide)
---
> 本指南彙整了六大緩存策略、實務選擇原則，以及系統設計中必須面對的三大緩存問題（穿透、雪崩、驚群）與解決方案。

參考資料
- [Caching Strategies Explained: System Design Fundamentals for Beginners](https://www.youtube.com/watch?v=TaYx0ReJWxE)
- [後端工程師面試考什麼 — 快取模式篇(cache patterns)](https://myapollo.com.tw/blog/interview-question-cache-patterns/)
---

## I. 讀寫策略與選擇原則

在實務上，系統會將讀取 (Read) 策略與寫入 (Write) 策略分開選擇並混合使用，以達到性能、成本和資料一致性的最佳平衡。

| 策略分類 | 主要目的 | 涵蓋策略 |
| :--- | :--- | :--- |
| **讀取策略** | 提升響應速度與吞吐量，處理 Cache Miss。 | Cache Aside, Read Through, Refresh-Ahead |
| **寫入策略** | 確保資料的持久性與最終/強一致性。 | Write Through, Write Behind, Write Around |

---

### A. 讀取策略 (Read Strategies)

#### 1. Cache Aside (旁路緩存)
最常見的模式，**App 程式碼**負責協調 Cache 與 DB。

* **流程**：App 查 Cache → Miss → App 查 DB → App 更新 Cache。
* **優點**：架構簡單、**容錯性高** (Cache 宕機不影響 DB)。
* **缺點**：首次讀取慢 (Miss Penalty)；程式邏輯承擔雙重職責。

{{< plantuml >}}
@startuml
title Cache Aside Read
skinparam backgroundColor #EEEBDC
participant "Application" as App
participant "Cache" as Cache
database "Database" as DB

group Read Operation
    App -> Cache: Get Key
    alt Cache Hit
        Cache --> App: Return Value
    else Cache Miss
        App -> DB: Query Data
        DB --> App: Return Data
        App -> Cache: Set Key, Value
    end
end
@enduml
{{< /plantuml >}}

#### 2. Read Through (讀穿)
App 只與 Cache 互動，**Cache 組件內部**負責處理 Miss 時的 DB 查詢與資料加載。

* **流程**：App 查 Cache → Miss → Cache 查 DB → Cache 更新自己 → 回傳 App。
* **優點**：**App 邏輯最簡單**。
* **缺點**：需要 Cache Provider 支援 Loader；Cache 模組複雜。

{{< plantuml >}}
@startuml
title Read Through
skinparam backgroundColor #EEEBDC
participant "Application" as App
participant "Cache" as Cache
database "Database" as DB

App -> Cache: Get Key
alt Cache Miss
    Cache -> DB: Load Data
    DB --> Cache: Return Data
    Cache -> Cache: Update Store
end
Cache --> App: Return Value
@enduml
{{< /plantuml >}}

#### 3. Refresh-Ahead (預先更新)
在資料過期前，Cache 自動預測並在背景刷新資料。

* **優點**：**消除 Cache Miss 延遲**，用戶體驗極佳。
* **缺點**：若預測不準，浪費資源更新冷資料。

---

### B. 寫入策略 (Write Strategies)

#### 4. Write Through (寫穿)
**同步**更新 Cache 與 DB，確保強一致性。常與 Read Through 搭配。

* **流程**：App 寫 Cache → Cache **同步**寫 DB → 雙寫成功才返回。
* **優點**：**強一致性 (Strong Consistency)**。
* **缺點**：**寫入延遲高**；可能造成 Cache 污染 (Cold Data)。

{{< plantuml >}}
@startuml
title Write Through
skinparam backgroundColor #EEEBDC
participant "Application" as App
participant "Cache" as Cache
database "Database" as DB

App -> Cache: Write Key, Value
Cache -> DB: Write Data (Sync)
DB --> Cache: Acknowledge
Cache --> App: Success
@endumal
{{< /plantuml >}}

#### 5. Write Behind / Write Back (寫後 / 非同步寫入)
App 寫入 Cache 立即返回，Cache 在背景**非同步**寫入 DB。

* **流程**：App 寫 Cache → 立即返回 → Cache **非同步**寫 DB。
* **優點**：**寫入效能極高**，適合寫入頻繁的場景。
* **缺點**：**資料遺失風險** (若 Cache 在寫 DB 前當機)；僅提供**弱一致性**。

{{< plantuml >}}
@startuml
title Write Behind
skinparam backgroundColor #EEEBDC
participant "Application" as App
participant "Cache" as Cache
database "Database" as DB

App -> Cache: Write Key, Value
Cache --> App: Success (Ack)
note right of Cache: Async Process
Cache -> DB: Write Data (Later)
@endumal
{{< /plantuml >}}

#### 6. Write Around (繞寫)
寫入時直接寫入 DB，**繞過 Cache**。常與 Cache Aside 搭配。

* **流程**：App 直接寫 DB，**不碰 Cache**。
* **優點**：**防止 Cache 污染**，只讓熱點資料透過讀取流程進入 Cache。
* **缺點**：剛寫入的資料立即被讀取，會產生 Cache Miss。

{{< plantuml >}}
@startuml
title Write Around
skinparam backgroundColor #EEEBDC
participant "Application" as App
participant "Cache" as Cache
database "Database" as DB

App -> DB: Write Data directly
note right of App
  Cache is bypassed.
  Data loads only on next Read Miss.
end note
@endumal
{{< /plantuml >}}

---

## II. 核心緩存問題與解決方案

### 1. 緩存穿透 (Cache Penetration) 💥

**問題**：查詢**不存在於 DB 和 Cache** 中的 Key，導致每次請求都穿透 Cache 直達 DB。

| 解決方案 | 說明 |
| :--- | :--- |
| **緩存空值 (Cache Null Object)** | DB 返回空時，將 Key 存為空值標記並設定短 TTL，阻止後續穿透。 |
| **布隆過濾器 (Bloom Filter)** | 在查詢到達 Cache 前，先檢查 Key 是否存在，對於**確定不存在**的 Key 直接拒絕。 |

### 2. 驚群效應 (Thundering Herd) 🌩️

**問題**：大量請求同時湧入一個**熱點資料**，且該資料的 **TTL 同時過期**，所有請求同時衝向 DB。

| 解決方案 | 說明 |
| :--- | :--- |
| **鎖機制 (Mutex)** | 第一個 Miss 請求獲取**鎖**，去 DB 查詢；其他 Miss 請求等待鎖釋放，避免重複查詢 DB。 |
| **隨機 TTL 分散化** | 對不同 Key 設定**隨機**的到期時間（例如 $60 \pm 5$ 秒），將過期時間錯開。 |

### 3. 緩存雪崩 (Cache Avalanche) ❄️

**問題**：在短時間內，**大量不同的 Key** 同時失效（因 Cache 服務器宕機或 TTL 設定一致），導致系統失去緩存能力。

| 解決方案 | 說明 |
| :--- | :--- |
| **高可用性架構 (HA)** | 使用 Redis Cluster 或 Sentinel 模式，確保單一節點故障時，仍有備援節點提供服務。 |
| **多級緩存 (Multi-Layer Cache)** | 增加一層本地緩存 (L1 Cache)，即使 L2 分佈式 Cache 宕機，仍有基本防禦。 |

---

## III. 總結比較表 📊

| 策略 | 讀取邏輯 | 寫入邏輯 | 一致性 | 寫入延遲 | 適用場景 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Cache Aside** | App 協調，Miss 才載入 | Update DB, Delete Cache | **最終一致** | 中 | **通用**，讀多寫少 |
| **Read Through** | Cache 負責載入 | (讀取策略) | - | - | **簡化 App 代碼** |
| **Write Through** | - | Cache **同步**寫 DB | **強一致** | **高 (慢)** | **一致性要求高**，如金融交易 |
| **Write Behind** | - | Cache **非同步**寫 DB | 弱 (有資料遺失風險) | **極低 (快)** | **寫入頻繁** (Write Heavy) |
| **Write Around** | - | 直寫 DB，繞過 Cache | 最終一致 | 中 | **避免冷資料污染** Cache |