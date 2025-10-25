---
date: 2019-10-18 11:11:48
draft: false
slug: System-Design-Overview
tags:
- system design
title: System Design Overview
---

## Introduction System Design
from jiuzhang, talk to you how to prepare your system
<!-- more -->
- DAU: Daily active user
- Infrastructure
- Web development
- analyst duo dilgence

    - work solution
    - special case
    - analysis
    - tradeoff
    - knowledge base
- 4s' analysis
    - scenario
    - service
    - storage
    - scale
- Design systems v.s. Design portion of systems (limit rate of access rate/statistical history)

## Breakdown The 
### Requirements
- **daily active users**
    - login/register
- **user profile**
    - display/edit
- **storage**
    - database: sql database => user table
    - nosql database => tweets/social graph
- **file system**
    - media files

- **cache**
    - nonpersistent

### algorithm/datastructure
- merge k sorted arrays
- Design user system - database& memcache
- design user system - memcached
- authentication
- sql vs nosql
- friendship (MST, kruskal, Prim)
- how to scale
- sharding/ consistent hashing/ replica

user systems features
- heavy read, light write
    - cache
    - a sort of key-val datastructure, like hashmap in Java
    - memcached => non-persistence (high performance)
    - redis => persistence (high cluster)
    - it is not necessary to keep in memory
        - file system could be a cache
        - cpu also has a cache

```python
cache.get("this is a key", "this is a value")
cache.get("this is a key")
```
`>> this is a value`
```python
cache.set("foo", 1, ttl = 60) // expired within 60 sec
cache.get("foo")
```
`>> 1`

```python
#wait for 60 seconds
cache.get("foo")
```
`>>null`
```python
cache.get("bar")
```
`>>null`


```python
# memcached optimize the query of DB
class UserService:
    def getUser(self, user_id):
        key = "user::%s" % user_id
```
### How to keep login?

#### session / login
After users login, server will create a session instance, and response `session_key` as a `cookie` back to a browser.

The browser will put the records in the cookie. Customers want to request the service every time. The browser will bring the cookie corresponding to the server, and the server will validate the session_key in cookie. If it is valid, the customer is allowed to access the services.

#### session logout

The server will erase/delete a record from a session table. But where is the session table.

In general, session table is stored in cache. However, it could be better when stored in database. If customers access frequently, try to adopt cache instead.

### SQL v.s. NOSQL
- transaction -> cannot use nosql
- sql -> serialization, secondary index and soon
- HDrive nosql run 10x+ fast than sql
- SQL
    - A column is defined by schema with predefinition, and cannot be abitrarily extended. Retrieve record by row
- NOSQL, opposite to SQL
    - column is dynamic
    - retrieve data by grid