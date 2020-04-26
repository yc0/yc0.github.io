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
$ oc exec -it {podname} -- {command} {--options}

$ oc exec -it {podname} -c {container} -- {command} {--options}
```

shorter equivalent

```bash
$ oc rsh {podname}
```
### Note
why we need -- ?
- You must use two dashes (--) to separate your command's flags/arguments

# Identity Providers 

## Concept
![](https://user-images.githubusercontent.com/10542832/79710264-10496580-82f7-11ea-9b09-2d000623a33b.png)

## Describe
### User
- Users are entities
- An actor within the system
- Interact with the API server
- Assign permissions by adding roles
- The user is a member of the group

### Identity
- A resource that keeps **a record** of **successful authentication** attempts from a specific user and identity provider
- A single user resource is associated with an identity resource.

### Service Account
- Applications can communicate with the API independently 
- Service accounts enable you to control API access with Service Account credentials.

### Group
- Groups represent a specific set of users
- Users are assigned to one or to multiple groups.
- implementing authorization policies to assign permissions **to multiple users at the same time.** 

### Role
- A set of permissions that enables a user to perform API operations over one or more resource types. `(Verb + Resources)`


## Summary

### Creating Users 
Requires valid credentials managed by an identity provider, user and identity resources

### Deleting Users
Deleting their credentials from the identity provider, and also deleting their user and identity resources.

### Two authentication methods
- kubeconfig : not recommand, super priviledge.
- kubeadmin virtual user

### OAuth Custom Resource
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
$ oc policy add-role-to-user view developer -n test-namespace
```
- add-role-to-group
- remove-role-from-user
- remove-role-from-group

### Cluster Scope
- add-cluster-role-to-user
- add-cluster-role-to-group
- remove-cluster-role-from-user
- remove-cluster-role-from-group

## Who can
`oc adm policy who-can {verb} {resource}`

for example
```bash
$ oc adm policy who-can create projects
```
However, in OpenShift, you cannot directly `create project` as prioi to mention.

OpenShift adopts a mechanism `projectrequest` resource to automatically on the background for making sure **the project** is created according to certain of settings and 

## Admin Role V.S. Edit Role
- no role related resources on Edit Role
- no delete/patch/update permission for projects and namespaces on Edit Role

## Service Account, SA
- exist within **the scope of a project**
    - that is to say, if there're the SAs with the same name, they are totally different objects though.




# Security Context Constraints, SCC

## Concept 
- it evaluates **at pod creation time**
    - Pod is with the correct SCC, it has to be deleted and be recreated
- it controls
    - Running privileged containers
    - Requesting extra capabilities to a container
    - Using host directories as volumes
    - Changing the SELinux context of a container
    - Changing the user ID



## Capabilities

Also refer to **POSIX capabilities**, you can look up piece of information in Linux.
The capabilities would be add or remove from the processes running inside the containers 
```bash
$ man 7 capabilities
```


## Prioitization

1. highest priority first, nil is considered a 0 priority
2. if priority is equal, most restrictive is with high priority

## Add SCC

```bash
$ oc adm policy add-scc-to-user {scc} -z {sa_name} -n {namespace} 
```
or more straighward

```bash
$ oc adm policy add-scc-to-user {scc} system:serviceaccount:{namespace}:{sa_name}
```

for example
```bash
$ oc adm policy add-scc-to-user noroot system:serviceaccount:troube:privileged
```


## Service Account to DeploymentConfig

```bash
$ oc set serviceaccount deploymentconfig {deployconfig} {service acccount}
```

it can be expressed shorter

```bash
$ oc set sa dc {dc} {sa}
```


## Summary
- ![](https://user-images.githubusercontent.com/10542832/79726062-c96e6680-831c-11ea-9129-9fc372ce6b13.png) 
Main concept of Role-based access control, RBAC
- Secret resources allow you to separate sensitive information from application pods
    - project scope
    - extract it for extension (configmap as well)

- Security context constraints (SCCs) t allowed pod interactions with system resources.

## Abbreviation
- mcs : multiple category security

# Components

## DeploymentConfig

### Concept
![](https://user-images.githubusercontent.com/10542832/79877134-711f8d80-841e-11ea-859c-cb514d4d7747.png)

## Networking

keypoints : **Troubleshoot it** and **ingress component**

### Service
- Kubernetes service IP == Virtual IP
- Doesn't allocate any unit/instance 
- A **collection** of network translation rules
- 4 types
    - cluster IP
    - node port [older concept]
    - load balancer [older concept] : alway along with cloud providers
    - service name
    ![](https://user-images.githubusercontent.com/10542832/80056079-ee015300-8555-11ea-886b-85f6d7e0ba0d.png)
### CoreDNS creates two records
    - A record : resolve FQDN to IP address
    - SRV record: what port the service uses.
        - if you use a service exposed TCP 443 through the `https` service in `frontend` namespace
        - `_443._tcp.https.frontend.svc.cluster.local`
        

### Cluster Network Operator 
can only be configured at installation time

#### NetworkType
- openshiftSDN : 3 types
    - network policy (default)
        - no policy == subnet mode
    - multitenant mode: project-level isolation
        - Pods from different projects cannot communicate with each other
        - unless we create network bridge between them
    - subnet mode (older default, ocp 3.*)
        - flat network
        - Pods can communicate with other Pods whereever their projects

### Route
- Ingress in Kubernetes
- Reverse Proxy
- When you create `route`
    - name of service
    - hostname of route

#### Types
There're four types:
- service  
- edge terminated route
- re-encrypted route
- passthrough

![router type](https://user-images.githubusercontent.com/10542832/80170176-f8852080-8619-11ea-97b9-04a578176c84.png)


### Summary
- OpenShift implements a software-defined networking (SDN) to manage the network infrastructure
- `Service` allow the logical grouping of pods
- `Service` acts as load balancer as well
- `Service` selects pods by labels
- Two route : `secure` and `insecure`
    - secure : TLS
        - edge
        - passthrough
        - re-encryption

# Scheduling
## OpenShift pod scheduler algorithm
1. Filtering nodes.
    - node condition : disk or memory pressure
    - match labels
    - pod resource demands : CPU, Memory and Storage
    - Taint
2. Prioritizing the filtered nodes
    - Affinity
3. Select a fit node

can possible create customerized scheduling policies with  `policy.cfg` key 

## Labeling on Node
Apart from tranditional way of labelling,
CLuster administrator can use `-L` to determine the single label

```bash
$ oc get node -L failure-domain.beta.kubernetes.io/region
```

## Labeling Machine Sets
Although node labels are persistent, if your OpenShift cluster contains machine sets (created if your cluster was installed using the full stack automation method, IPI), you should add labels to the `MachineSets`

This ensures that new machines will also contains the desired labels when generating new nodes.

## Controlling Pod Placement
### Infrastructure-related Pods
- run on master nodes
- DNS Operator
- OAuth operator
- API Server

### Node Selector
```bash
$ oc edit deployment/myapp
```
```yaml
spec:
...output omitted...
  template:
    metadata:
      labels:
        app: myapp
    spec:
      nodeSelector:
        nev: dev
      containers:
      - images: quay.io/redhattraining/scaling:v1.0
...output omitted...
```
the following command accomplishes the same thing
```bash
$ oc patch deployment/myapp --patch \
'{"spec":{"template":{"spec":{"nodeSelector":{"env":"dev"}}}}}'
```

Both commands triggers new deployemnt and new pods scheduled according to the node selector

## Default Node Selector for a Project

default node selector should be configured in the project resource, for example:

### create a new project

```bash
$ oc admin new-project qa --node-selector "env=qa"
```

### configure on a existing project

```bash
$ oc annotate namespace qa \
openshift.io/node-selector="env=qa" --overwrite
```

## Scaling
```bash
$ oc scale --replicas 3 deployment/myapp
```

# Limiting Resource Usage
## Resource Requests
- Used for scheduling, scheduler find a node with sufficient compute resources.
- indicate that a pod cannot run with less than the specified amount of compute resources. 
## Resource limits
- how far Pod can consume the resources
- prevent a pod from using up all compute resources from a node
- Linux kernel cgroups feature to enforce the resource limits for the pod.

## Observation

the individual resource comsumption for a pod or the sum amount of the resource comsumption

### By Describe
```bash
# oc describe node/{node}
$ oc describe node ip-10.10.0.0.us-east-1.compute.internal 
```

### By Node type 
```bash
# oc adm top node
# 
$ oc adm top node -l node-role.kubernetes.io/worker
```

### By project
```bash
$ oc adm top node -n execute-troubleshoot
```

## Quality of Service
1. BestEffort
    - first eviction
2. Burstable
    - second evition
3. Guaranteed
    - never evition
    - unless go node down for maintenence

## Quota
Quotas are limitations on the aggregate consumption of resources of any particular project

### Two kinds
- Object counts
- Compute resources 

### Improve stablility of the OpenShift
- Avoiding unbounded growth of the Etcd database
- Avoids exhausting other limited software resources, e.g. IP.

## Some important Note of Quota
### Best-Effort Node
Any Node with resourcequota cannot accommodate any `best-effort` node
### Multiple Resource Quota in a project
Though we can create multiple `resourcequota`, we cannot overlap the quota items in the same project

## Limit Ranges
- give range min limits to max limits
- give deault limits for containers w/o the requests and limits specified

### Some Pods, System Pods
- Deployer pod
- Builder Pod

## ClusterQuota
- project-annotation-selector
- project-label-selector

## Lookup

project scale
```bash
$ oc describe resourcequota
```

cluster span mulitple project
```bash
$ oc describe appliedclusterresourcequotas
```

due to `request quota`, there's not allowed `best effort` Pods. It brings the situation to setup default - `Limit Range`.

# Scale
## Manual Scaling
```bash
$ oc scale deployment/psql --replicas=3
#or
$ oc scale dc/psql --replicas=3
```
the difference between dc and deployment is that dc adopts replicacontroller whereas deployement adopts replicsets. Basically they are with same mechanism

## Autoscaling
### Concept
![autoscaling](https://user-images.githubusercontent.com/10542832/80303941-cfb18680-87e5-11ea-9c32-9caeacfb3336.png)

### Matrix subsystem
- OCP4 pre-installed
- OCP3 it's a part of the platform
    - take care of separately
### Command

```bash
$ oc autoscale dc/mysql --min=1 --max=5 --cpu-percent=80
```
### Controller by HorizontalPodAutoscalar, HPA

Remember that if you want to specify cpu-percent, you must request resources `burstable or guaruanteed`

## Summary
- Default pod scheduler spans regions and zones : performance and redundancy.

- Pod placement use node selectors w/ labeling nodes.

- Resource requests : the minimum amount of resources for scheduling.

- Quotas : restrict the amount consumption of resources a project.

- scales number of replicas of a pod
    - `oc scale` for manual
    - `oc autoscale` for dynamic 

# Scaling an OpenShift Cluster
## Machine API gives 2 custom resources
### `machine-api` operator
- handle machine-api
- handle machine
- two 2 CRD
    - Machineset
    - machine

```bash
$ oc get clusteroperators

$ oc get clusteroperators/machine-api
$ oc get -n openshift-machine-api machines
$ oc get -n openshift-machine-api machinesets
```

- modify Machineset
    - won't affect existing machines
    - only new machine inherit the features
    - analogous to how `ReplicaSet` treat pods
### `machine-config` operator
    - handle vm or instance
    - help it become worker node

# Tips
## List Project
```bash
$ oc projects
```

## Check CRD
```bash
$ oc get clusteroperators

# oc get clusteroperators/{operator}
$ oc get clusteroperators/dns

# oc get -o yaml {crd}.operator/{name}
$ o get -o yaml dns.operator/default
```

## Copy Data
```bash
# oc cp {source} {pod}:{target}
$ oc cp data.sql mysql-5cpd:/tmp/
```

## Check Pod/Deployment Mount
```bash
# oc set volumes deployment/{name}
# oc set volumes pod/{name}

$ oc set volumnes deployment/mysql
```

## Labelling on Node
```bash
# add new labels
$ oc label node node1.us-east-1.compoute.internal env=dev  
# modify existing labels
$ oc label node node1.us-east-1.compute.internal env=dev --overwrite
# remove labels
$ oc label node node1.us-east-1.compute.internal env-
```

## Control Quota
```bash
$ oc create quota count -n test \
 --hard=services=5,pods=25,replicationcontrollers=17....

$ oc create quota compute -n test \
 --hard=cpu=5,memory=4Gi,limits.cpu=7,limits.memory=8Gi

```

## Retry Schdule
```bash
$ oc rollout retry dc/{name}
$ oc rollout latest dc/{name}
```

