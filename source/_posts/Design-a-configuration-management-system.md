---
title: Design a configuration management system
date: 2019-10-22 16:40:02
tags: ['system design','amazon','onsite']
categories: ['system design']
---

## Configuration management system

Design a configuration management system

- User should be able to add configuration
- User should be able to delete configuration
- User should be able to search for configuration
- User should be able to subscribe to Configuration So that any updates in configuration will gets notfied to user

### Clarify

We want to design a system to persist configurations that can be used by other systems. Configurations will be managed through an internal portal and will be editable only by the user who created them but can be read by any system through a RESTful API. In addition to CRUD (creation, read, updates and deletions) an user can search for configurations and can subscribe to them to receive notifications every time there's a change.

This is how I'd go about it (since I don't have an interviewer to ask questions to, these numbers are made up):

### Assumptions

- Let's say we have 500M total users and 50M daily active users
- There are 1M new configurations created every day on average
- We get 100M reads of the configurations every day on average
- Updates are infrequent but they happen: 10k a day on average
- Deletions are even more infrequent: 5k a day on average
- Each active user performs 2 searches a day on average
- 5k subscriptions every day, 0.5k unsubscriptions a day on average
- Configurations are JSON files that are 1kb in size on average
- Following the CAP theorem, we can argue that we are interested in an AP system (highly available, partitioned and eventually consistent).

With this data, I'd do some back-of-the-envelope math:

- Traffic: Calculate the read TPS and write TPS.
- Bandwidth: download and upload bandwidth necessary to serve the content
- Memory: how much memory we are going to need to store 5 and 10 years of configurations * (see below for this)
- Cache: following the 80/20 rule, calculate how much memory we need to store 20% of daily configurations * (see below for this)

To do number 3 and 4, we should sketch the models:

`Configuration Table:`

- ConfigurationID
- ConfigurationName
- OwnerID
- ConfigurationURI
- CreationTimestamp

We should estimate the length in bytes of the configuration ID to be able to hold 10 years of IDs. Same for ownerID.
Now that we've done some math, we probably found out the following:

1. The system is VERY read heavy:
    - Probably a good approach would be to have master write DBs where the changes are propagated to the slave read DBs.
    - Cache will benefit us immensely. Talk about eviction strategies.
2. The TPS will help us figure out how many web servers we need.
3. The memory will probably tell us that we need sharding. Discuss here sharding strategies and No SQL vs SQL databases.


Quickly sketch the APIs of the system and their parameters. At least we need the following APIs:

- CreateConfiguration
- UpdateConfiguration
- DeleteConfiguration
- ReadConfiguration
- SearchConfigurations
- SubscribeToConfiguration
- UnsubscribeFromConfiguration

After this, draw a HIGH LEVEL diagram (without scaling, load balancing, redundancy, cache etc.) to trace a request for each API:
```
                     |-----> IndexService --------v
User --> Web Server --> ConfigurationService --> Database
                     |-----> Cloud Storage
```

After that, we can move on to a detailed design:
```
User --> LoadBalancer --> [WebServer1, WebServer2, ...] --> Load Balancer --> [ConfigurationService1, ConfigurationService2,...] --> Cache --> MasterDatabases --> SlaveDatabases
```
### At least Cover the following


1. Load balancing and mention a couple of LB algorithms
2. What we're storing in the cache
3. What happens when Load Balancers die and how do you detect it
4. Redundancy: how we can guarantee that we wont lose any configurations
5. What happens when there's a spike of reads because it's Black Friday on Amazon
6. What happens if a Master Database dies
7. What happens if a slave database dies
8. What happens if the cache dies
9. Do we need a CDN?
10. How can we prevent users from storing highly sensitive data in there? Like Credit Card numbers.
11. What happens if a datacenter goes down? Can we recover from that? How?
12. Can we compress the configurations? How much space is that going to save? What's the impact in latency when reading a new configuration?
13. How can we throttle a user that wrote a buggy script and is creating configurations like crazy (and will consume all IDs)?
14. What metrics are you going to monitor?
15. Where do you store the logs? How often do you rotate them?
16. What alarming are you going to put in place?

