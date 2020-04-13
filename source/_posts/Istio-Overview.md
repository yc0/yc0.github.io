---
title: Istio Overview
date: 2020-04-13 17:16:32
tags: ['OpenShift','Istio','Overview','Network']
categories: ['OpenShift','Istio']
---

# Service Connection
## Traffice management
- service mesh traffic management decouples traffic flow and infrastructure scaling
- Pilot to specify rules for traffic management
- Pilot and Envoy manage which pods receive traffic
### Pilot
- **Manages and configures** Envoy proxy 
- specify **routing rules**
- Enables service **discovery**, **dynamic updates** for load balancing, routing tables
### Envoy
- Maintains configuration information from Pilot
## Request Routing
- Fine-grained approach to identify services by versions
- Service versions in OpenShift service mesh implemented with **OpenShift labels**
### Communication Between Services
- clients have **agnostic** of different service versions
- Envoy **intercepts**, forwards requests/responses between client and service
- Routing rules **configured with Pilot**
    - Header
    - Tags associated with SRC/DEST
    - Weight associated with Version
## Rule Configuration
- VirtualService : Defines rules that control how requests for service are routed within service mesh
- DestinationRule : correspond to one or more request destination hosts specified in VirtualService configuration

    - May or may not be same as actual destination workload

    - May not correspond to actual routable service in mesh

- ServiceEntry: Enables requests to services outside service mesh
- Gateway : Configures load balancer operating at edge of mesh for:
    - HTTP/TCP ingress traffic to mesh application
    - Egress traffic to external services
    - Sidecar Configures sidecar proxies attached to application workloads running inside mesh
## Traffic Splitting
- Each route rule identifies one or more weighted
- Versions expressed using labels
## Conditional Rules
- Can qualify rules to apply only to requests that match specific condition
```
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
metadata:
  name: ratings
spec:
  hosts:
  - ratings
  http:
  - match:
    - sourceLabels:
        app: reviews
        version: v2
  - match:
    - headers:
        From: 
          exact: webmaster@example.org
 ```