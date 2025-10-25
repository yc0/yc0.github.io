---
date: 2020-04-04 16:29:07
draft: false
slug: kubernetes-scratch
tags:
- kubernetes
- imperative
title: kubernetes scratch
---

## Quick Overview
### kubernetes .io
- [Getting started](https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#-em-deployment-em-)

### create pod
`kubectl run --generator=run-pod/v1`

for example

`kubectl run --generator=run-pod/v1 bee --image=nginx`

### alias

- cheat sheet
`https://kubernetes.io/docs/reference/kubectl/cheatsheet/`

### other
```
alias k='kubectl -n $ns'

alias kdr='kubectl run -n $ns -o yaml 
--dry-run'

alias kpr='kubectl run --generator=run-pod/ v1 -n $ns -o yaml --dry-run'
```


### Shell
#### Get rid of the first line and recliam first column
```
$ awk 'NR!=1{print $1}' file
```
#### Read follow line regarding to certain word
```bash
#grep -A{lines} {keyword}
$ grep -A3 'Labels'
```


#### Execution Tips
- Check Network Connection
    - [Netcat](https://blog.gtwang.org/linux/linux-utility-netcat-examples/)
    - example
    ```bash
    # kubectl exec -it {podname} -- sh
    $ nc -z -v -w1 {target} {port}
    ```

#### VIM Tips
- Auto indent and tab
```bash
se sts=2 sw=2 ai et
set nu rnu
```


##### 與自動縮進相關的變數表
變數名|縮寫|含義
:---|:---:|:---
(no)autoindent |ai | 自動縮進，即為新行自動添加與當前行同等的縮進
(no)cindent | ci | 類似C語言程序的縮進
(no)smartindent |si | 基於autoindent的一些改進

##### 與TAB相關的變數表
變數名|縮寫|含義
:---|:---:|:---|
tabstop=X|ts|編輯時一個TAB字元佔多少個空格的位置|
shiftwidth=X|sw|使用每層縮進的空格數
(no)expandtab|(no)et|是否將輸入的TAB自動展開成空格。開啟後要輸入TAB，需要Ctrl-V<TAB>
softtabstop=X|sts|方便在開啟了et後使用退格（backspace）鍵，每次退格將刪除X個空格
(no)smarttab|(no)sta|開啟時，在行首按TAB將加入sw個空格，否則加入ts個空格