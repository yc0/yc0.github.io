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
# Trouble Shooting

## oc adm node-log
## oc log
```bash
oc logs {podname} --all-containers
oc logs {podname} -c {}
```

## oc debug
- what went wrong during POD startup 
- `oc debug {pod|deployment} --as-root`

## oc rsh
```bash
> oc exec -it {podname} -- {command} {--options}

> oc exec -it {podname} -c {container} -- {command} {--options}
```

shorter equivalent

```bash
> oc rsh {podname}
```

# Identity Providers 

## Concept
![](https://user-images.githubusercontent.com/10542832/79710264-10496580-82f7-11ea-9b09-2d000623a33b.png)

## Describe
#### User
- Users are entities
- An actor within the system
- Interact with the API server
- Assign permissions by adding roles
- The user is a member of the group

#### Identity
- A resource that keeps **a record** of **successful authentication** attempts from a specific user and identity provider
- A single user resource is associated with an identity resource.

#### Service Account
- Applications can communicate with the API independently 
- Service accounts enable you to control API access with Service Account credentials.

#### Group
- Groups represent a specific set of users
- Users are assigned to one or to multiple groups.
- implementing authorization policies to assign permissions **to multiple users at the same time.** 

#### Role
- A set of permissions that enables a user to perform API operations over one or more resource types. `(Verb + Resources)`

## Summary
#### Creating Users 
Requires valid credentials managed by an identity provider, user and identity resources

#### Deleting Users
Deleting their credentials from the identity provider, and also deleting their user and identity resources.

#### Two authentication methods
- kubeconfig : not recommand, super priviledge.
- kubeadmin virtual user

#### OAuth Custom Resource
- HTPasswd Identity Provider
    - htpasswd
    - extract data from secret/store in a secret
- Assign `cluster-admin` role to the user to grant a user cluser admin priviledge.

# Role-based Access Control, RBAC
 In OpenShift, RBAC determines if a user can perform certain actions within the cluster or project. There're two types of roles:
 - Cluster
 - Local.

## Concept
![rbac](https://user-images.githubusercontent.com/10542832/79726062-c96e6680-831c-11ea-9129-9fc372ce6b13.png)

## Project V.S. Cluster
Actually for rolebinding resource creation

### Project Scope
- add-role-to-user
`oc policy add-role-to-user {role} {user} {-n option}`

it's better to assign specific namespace to make sure we delegate the designate namespace toward user

for example

```bash
oc policy add-role-to-user view developer -n test-namespace
```
- add-role-to-group
- remove-role-from-user
- remove-role-from-group

### Cluster Scope
- add-cluster-role-to-user
- add-cluster-role-to-group
- remove-cluster-role-from-user
- remove-cluster-role-from-group

### Who can
`oc adm policy who-can {verb} {resource}`

for example
```bash
oc adm policy who-can create projects
```
However, in OpenShift, you cannot directly `create project` as prioi to mention.

OpenShift adopts a mechanism `projectrequest` resource to automatically on the background for making sure **the project** is created according to certain of settings and 

### Admin Role V.S. Edit Role
- no role related resources on Edit Role
- no delete/patch/update permission for projects and namespaces on Edit Role

### Service Account, SA
- exist within **the scope of a project**
    - that is to say, if there're the SAs with the same name, they are totally different objects though.

# Resource

## DeploymentConfig

### Concept
![](https://user-images.githubusercontent.com/10542832/79877134-711f8d80-841e-11ea-859c-cb514d4d7747.png)