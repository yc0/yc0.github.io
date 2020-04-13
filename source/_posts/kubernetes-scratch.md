---
title: kubernetes scratch
date: 2020-04-04 16:29:07
tags: ['kubernetes','imperative']
categories: ['cloud native', 'kubernetes']
---

## Quick Overview
#### kubernetes .io
- [Getting started](https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#-em-deployment-em-)

#### create pod
`kubectl run --generator=run-pod/v1`
for example
```kubectl run --generator=run-pod/v1 bee --image=nginx```

#### alias

- cheat sheet
`https://kubernetes.io/docs/reference/kubectl/cheatsheet/`

- other
    ```
    alias k='kubectl -n $ns'
    alias kdr='kubectl run -n $ns -o yaml   --dry-run'
    alias kpr='kubectl run --generator=run-pod/ v1 -n $ns -o yaml --dry-run'
    ```



#### Shell
- Get rid of the first line and recliam first column
    ```
    awk 'NR!=1{print $1}' file
    ```