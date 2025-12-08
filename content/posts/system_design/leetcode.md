---
date: '2025-11-28T00:00:00+08:00'
draft: true
categories:
  - system design
title: Online Judge / Coding Platform（LeetCode 類）
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