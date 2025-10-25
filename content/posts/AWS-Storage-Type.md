---
date: 2019-10-01 11:59:16
draft: false
slug: AWS-Storage-Type
tags:
- AWS
- Storage
title: AWS Storage Type
---

## AWS儲存型式

Recently, we dicussed that how to supply storages for persistent volumes of Kuberenetes. There're plenty of types shown on official website. Many peopel including my folks don't realize what are the difference and what are they suitable for ? As a solution architect, there're no absoluate answer for an answer. It depends on what kind of applications you face. Today, I want to mention two types : block-based(BLK) and file-based storage(NFS) , and counterparts in AWS. The materials come from Business Professional Accrediated

### AWS EBS
- useful fro file-based workloads
- enterprise application
- relational database
- NOSQL database
- application where consistency & **low-latency** performance is required

In sum, low-latency and log-file- based databases whatever for transaction solutions, such as WSREP, WAL or partitioned files in Kafka, are all suitable for EBS.

### AWS EFS
A managed-services of NFS in AWS.
- file storage server
- create and configure file systems
- capacity is elastic
    - grow and shrink automatically as files are added or removed

In sum, just like traditional file storage server with elasticity, but you might occur a little bit latency due to propagation for consistency. 