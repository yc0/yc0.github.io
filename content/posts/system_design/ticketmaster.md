---
date: '2025-11-24T00:00:00+08:00'
draft: true
categories:
  - system design
  - distributed lock
title: Ticketing System（Ticketmaster 類)
---
## 3. Ticketing System（Ticketmaster 類）

### 3.1 題目重述與假設

- 題目：設計一個線上售票系統（演唱會 / 球賽）。  
- 功能需求：  
  - 查詢活動、場次、座位區域與價格  
  - 選位、鎖座、付款、出票  
  - 防止超賣、避免同一座位被重複購買  
- 非功能需求：  
  - 高峰流量：開賣瞬間激增（瞬間數十萬人搶票）  
  - 極高一致性需求：不能 oversell 某個 seat  
  - 容許部分操作排隊或等待  

### 3.2 高階架構說明

- Seat inventory model：每個 event / section / seat 有一筆紀錄，包含狀態（available / reserved / sold）。  
- 流程：  
  - 查詢座位圖：讀取 cache / DB 中的 seat map。  
  - 用戶選位時：在 Seat Service 上做 lock（短時間 hold），寫入 `reserved_by = user_id`，同時用 TTL。  
  - 用戶完成付款：Payment 成功後，Seat Service 將 seat 狀態轉為 sold。  
  - 用戶未在期限內付款：background job 過期保留，釋放 seat。  
- 為防 oversell：Seat Service 要用強一致操作（例如：Row-level lock / compare-and-swap / Redis 分布式鎖）。  

### 3.3 PlantUML

{{< plantuml >}}
@startuml
title Ticketing System - High Level Architecture

actor User
rectangle "Web / Mobile Client" as CLIENT

rectangle "API Gateway" as API
rectangle "Event & Seat Service" as SEAT
database "Seat Inventory DB" as SEATDB

rectangle "Order Service" as ORDER
database "Order DB" as ORDERDB

rectangle "Payment Service" as PAY
queue "Reservation Expiry Queue" as EXPQ

User --> CLIENT : browse / buy tickets
CLIENT --> API : search events / seats
API --> SEAT : get seat map
SEAT --> SEATDB : read seat status

CLIENT --> API : reserve seats
API --> ORDER : create pending order
ORDER --> SEAT : lock seats (reserve)
SEAT --> SEATDB : update seat state=reserved

ORDER --> EXPQ : push reservation TTL

CLIENT --> API : pay order
API --> PAY : charge payment
PAY --> ORDER : payment result
ORDER --> SEAT : confirm seats (sold)
SEAT --> SEATDB : state=sold
ORDER --> ORDERDB : update order status=PAID

' Reservation expiry
EXPQ --> ORDER : reservation timeout
ORDER --> SEAT : release seats
SEAT --> SEATDB : state=available

@enduml
{{< /plantuml >}}

### 3.4 口頭講稿（約 2–3 分鐘）

> 這一題的核心是 seat inventory 的一致性管理。我要確保同一張椅子不會被兩個人買到。  
> <br>
> 我會設計一個 Seat Service，背後有 Seat Inventory DB，存每個 event/seat 的狀態。當使用者選位時，會走 reserve 流程：Seat Service 在資料庫中把該座位從 available 改成 reserved，並標註 reserved_by，這個更新操作必須是原子性的，例如用 row-level lock 或條件更新。  
> <br>
> 產生的訂單狀態會先是 pending，同時放一個訊息進 Reservation Expiry Queue。使用者完成付款後，Order Service 會將訂單狀態改為 PAID，並把 seat 狀態改為 sold。如果超過 TTL 還沒付款，Background job 根據 queue 事件回來通知 Order Service 取消訂單並釋放 seats。  
> <br>
> 開賣高峰時，可以用 queue / waiting room 來平滑請求，Seat Service 可以透過分區和讀寫分離來 scale。  

---
# Ticketmaster System Design: 座位庫存管理與鎖定機制

這份文件總結了關於 Ticketmaster 類型的票務系統設計討論，重點在於如何處理高併發下的座位庫存管理（Inventory Management）。

## 1. 初始構想：基於 Topic Queue 的架構

### 提問
系統目標是處理約 10 萬人/場，總共 100 萬張票的庫存。是否可以為**每個座位建立一個 Queue Topic**，由 Queue Service 來管理一致性？

### 分析：為什麼「單座位單 Topic」不可行？
雖然 100 萬個物件在資料庫中不多，但在 Message Queue (如 Kafka, Pulsar) 中是不可行的。

1.  **Metadata 管理崩潰 (Topic Explosion)**：
    * Kafka 等中介軟體並非設計來處理百萬級別的 Topic。過多的 Topic 會導致 Zookeeper/Controller 的 Metadata 管理壓力和 File Descriptor 資源耗盡。
2.  **讀取困難 (The View Problem)**：
    * 搶票是 **「讀多寫少」** 的場景。前端渲染 Seat Map 需要一次查詢數萬個座位的狀態。若使用 Queue，無法高效查詢所有 Queue 的當前狀態。
3.  **原子性難題 (Atomicity)**：
    * 購買連號座位（如 A1, A2）時，需同時從兩個 Queue 獲取訊息。若 A1 成功但 A2 失敗，回滾（Rollback）邏輯極其複雜，容易導致 Deadlock。

---

## 2. 架構比較與修正方案

如果堅持使用 Queue，必須調整粒度（例如：單場次單 Queue）。以下是不同方案的詳細對比：

| 特性 | 方案 A：單座單 Queue (你的提議) | 方案 B：單場次單 Queue | 方案 C：Redis + Lua (業界標準) |
| :--- | :--- | :--- | :--- |
| **Topic 數量** | 100 萬 (極高，不可行) | 100 ~ 1000 (可控) | N/A (不依賴 Queue) |
| **併發處理能力** | 差 (資源耗盡) | 中 (受限於 Consumer 處理速度) | **極高 (記憶體操作)** |
| **查詢選位圖** | 極慢 (需掃描大量 Queue) | 需額外 DB 支援 | **極快 (讀 Cache)** |
| **連號座位處理** | 極難 (分散式鎖問題) | 容易 (在 Consumer 記憶體內判斷) | **容易 (Lua 腳本一次判斷)** |
| **實作複雜度** | 極高 | 中 | 中 |

* **方案 B (Queue) 缺點**：熱門場次瞬間流量巨大，單一 Consumer 會成為瓶頸，導致使用者等待時間過長（Backpressure）。
* **方案 C (Redis) 優點**：利用記憶體原子操作，解決了鎖定與效能問題。

---

## 3. 推薦方案：Redis + Lua Script (業界標準)

目前高效能搶票系統的主流做法是結合 **Redis (Cache)** 與 **Database**。

* **Redis**：負責高併發的讀取與原子性鎖定 (Locking)。
* **Database**：負責最終的資料持久化 (Persistence) 與付款紀錄。

### 核心機制
利用 Redis 單執行緒特性配合 **Lua Script**，確保「檢查庫存」與「鎖定座位」是原子操作 (Atomic Operation)。

### 3.1 Lua Script 邏輯 (All-or-Nothing)
此腳本保證：要嘛所有選擇的座位都鎖定成功，要嘛全部失敗（避免買到不完整的連號）。

```lua
-- KEYS: 座位 Keys, 例如 {"{evt:1}:A1", "{evt:1}:A2"}
-- ARGV[1]: User ID
-- ARGV[2]: TTL (鎖定秒數)

-- 步驟 1: 檢查階段
-- 只要有一個座位已存在 (被鎖定或售出)，則全部失敗
for i, key in ipairs(KEYS) do
    if redis.call("EXISTS", key) == 1 then
        return 0 -- 失敗
    end
end

-- 步驟 2: 執行階段
-- 寫入鎖定資訊，並設定 TTL
for i, key in ipairs(KEYS) do
    redis.call("SET", key, ARGV[1], "NX", "EX", ARGV[2])
end

return 1 -- 成功
```

### 3.2 C++ 實作範例
使用 `redis-plus-plus` 函式庫示範如何呼叫上述腳本。

```cpp
#include <iostream>
#include <vector>
#include <string>
#include <sw/redis++/redis++.h>

using namespace sw::redis;

class SeatBookingSystem {
private:
    Redis _redis;
    std::string _lua_script_sha;

public:
    SeatBookingSystem(const std::string& uri) : _redis(uri) {
        // 系統啟動時載入 Lua Script 以優化頻寬
        std::string script = R"(
            for i, key in ipairs(KEYS) do
                if redis.call("EXISTS", key) == 1 then return 0 end
            end
            for i, key in ipairs(KEYS) do
                redis.call("SET", key, ARGV[1], "NX", "EX", ARGV[2])
            end
            return 1
        )";
        _lua_script_sha = _redis.script_load(script);
    }

    // 嘗試鎖定座位
    bool reserveSeats(const std::string& userId, const std::string& eventId, const std::vector<std::string>& seatIds) {
        std::vector<std::string> keys;
        
        // 組合 Key (使用 Hash Tag {} 確保在 Cluster 模式下位於同一 Slot)
        for (const auto& seat : seatIds) {
            keys.push_back("{evt:" + eventId + "}:seat:" + seat);
        }

        std::vector<std::string> args = {userId, "300"}; // TTL: 300秒

        try {
            long long result = _redis.evalsha<long long>(
                _lua_script_sha, 
                keys.begin(), keys.end(), 
                args.begin(), args.end()
            );
            return result == 1;
        } catch (const Error& e) {
            std::cerr << "Redis Error: " << e.what() << std::endl;
            return false;
        }
    }
};
```

---

## 4. 關鍵設計細節 (Deep Dive)

### A. TTL (Time To Live) 的重要性
* **用途**：處理當機、網路中斷或使用者放棄付款的情況。
* **機制**：Redis 會在 TTL 到期後自動刪除 Key，釋放座位回到庫存池。無需額外的 Cleanup Cron Job。

### B. Redis Cluster 與 Hash Tags
* **問題**：Redis Cluster 將資料分片到不同節點。Lua Script 要求所有操作的 Keys 必須在同一個 Hash Slot。
* **解法**：使用 **Hash Tags `{...}`**。
    * 錯誤：`evt:1:seat:A`, `evt:1:seat:B` (可能在不同機器)
    * 正確：`{evt:1}:seat:A`, `{evt:1}:seat:B` (強制根據 `evt:1` 計算雜湊，保證在同一台機器)

### C. 為什麼不直接用 DB?
* 關聯式資料庫 (RDBMS) 的 Row Lock 在高併發下（如每秒數萬次請求）會導致嚴重的效能下降和 Deadlock 風險。Redis 記憶體操作是此類「秒殺」場景的最佳解。