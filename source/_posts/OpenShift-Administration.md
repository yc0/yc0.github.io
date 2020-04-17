---
title: OpenShift Administration
date: 2020-04-15 23:00:38
tags:
---

# Describe OpenShift Container Platform

## Overview
- An application manages Kubernetes resources: Operator
- An application manages Kubernetes operators : Operator Lifecycle Manager(OLM)
- A repo. for discovering and installing operators : Operator Catelog
- Regular operators that are not managed by the OLM. They are managed by OpenShift Cluster Version Operator : Cluster Operators
    - OpenShift Cluster Version Operator : First-level operator
    - Cluster Operators are called second-level operators
## Summary
- Red Hat OpenShift Platform is based on Red Hat CoreOS, CRI-O and Kubernetes
- RHOCP 4 provides a number of services on top of Kubernetes, such as an internal container image registry, storage, networking providers, and centralized logging and monitoring.
- Operators package applications that manage Kubernetes resources, and the Operator Lifecycle Manager (OLM) handles installation and management of operators.
- OperatorHub.io is an online catalog for discovering operators.

# Installation
## IPI 
- Full-Stack Installation
- Only this way can fulfil cluster scaling
- http://try.openshift.org
- It does't have to **be part of cluster**

## UPI
- User provisioned Infrastructure for pre-existing environment

## CoreOS and RHEL
- Control Panel must run on CoreOS
- Workers can run either CoreOS or RHEL

## Installation-config.yaml
- the rest of resource domain name following 
  `{metadata.name} + {baseDomain}`
- network configuration cannot reconfigure easily after cluster is up and running.

## Initial deployment process
- there's no much customization
- UPI mode has to do node certficate when dial to master node (control plane) **by manual** whereas IPI has no requirment.

## Summary
- two main installation methods
    - full-stack automation
    - pre-existing infrastructures.
- OpenShift node based on Red Hat Enterprise Linux CoreOS runs very few local services 
- Most of the system run as containers
    - CRI-O and kubelet
- Troubleshooting
    - `oc get node`
    - `oc adm top`
    - `oc adm node-logs`
    - `oc adm debug`