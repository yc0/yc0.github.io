---
date: '2025-12-01T00:00:00+08:00'
draft: true
categories:
  - system design
title: Web Crawler
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