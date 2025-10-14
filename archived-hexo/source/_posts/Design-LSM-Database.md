---
title: Design LSM Database
date: 2019-10-23 11:41:20
tags: ['system design','amazon','LSM','onsite']
categories: ['system design', 'database']
---

## LSM Design Overview

The LSM stores data in three distinct data structures:

- The `shared-memory region`. This may actually be allocated in either shared or heap memory

- The log file. A circular log file that provides a persistent backup of the contents of the in-memory tree and any other data that has `not yet been synced to disk`.

- The database file. A database file consists of an 8KB `header and a body`. The body contains `zero or more "sorted runs"` - arrays of key-value pairs sorted by key.

To query a database, the contents of the in-memory tree must be merged with the contents of each sorted run in the database file. Entries from newer sorted runs are favoured over old (for the purposes of merging, the in-memory tree contains the newest data).

### In summary

LSM embedded database software stores data in three distinct data structures:
- The shared-memory region. This may actually be allocated in either shared or heap memory, depending on whether LSM is running in multi (the default) or single process mode. Either way, the shared-memory region contains volatile data that is shared at run-time between database clients. Similar to the *-shm file used by SQLite in WAL mode.

As well as various fixed-size fields, the shared-memory region contains the 'in-memory tree'. The in-memory tree is an append-only red-black tree structure used to stage user data that has not yet flushed into the database file by the system. Under normal circumstances, the in-memory tree is not allowed to grow very large.

- The log file. A circular log file that provides a persistent backup of the contents of the in-memory tree and any other data that has not yet been synced to disk. The log-file is not used for rollback (like an SQLite journal file) or to store data that is retrieved at runtime by database clients (like an SQLite WAL file). Its only purpose is to provide robustness.

- The database file. A database file consists of an 8KB header and a body. The body contains zero or more "sorted runs" - arrays of key-value pairs sorted by key.

To query a database, the contents of the in-memory tree must be merged with the contents of each sorted run in the database file. Entries from newer sorted runs are favoured over old (for the purposes of merging, the in-memory tree contains the newest data).

When an application writes to the database, the new data is written to the in-memory tree. Once the in-memory tree has grown large enough, its contents are written into the database file as a new sorted run. To reduce the number of sorted runs in the database file, chronologically adjacent sorted runs may be merged together into a single run, either automatically or on demand.

### Locks

Read/write (shared/exclusive) file locks are used to control concurrent access. LSM uses the following "locking regions". Each locking region may be locked and unlocked separately.

|Types   | 內容  |
|---|---|
| DMS1  | This locking region is used to serialize all connection and disconnection operations performed by read-write database connections. An EXCLUSIVE lock is taken for the duration of all such operations.　<br><br> Additionally, read-only connections take a SHARED lock on this locking region while attempting to connect to a database. This ensures that a read-only connection does not attempt to connect to the database while a read-write clients connection or disconnection operation is ongoing.|
| DMS2  | Read-write connections hold a SHARED lock on this locking region for as long as they are connected to the database.|
| DMS3  | Read-only connections hold a SHARED lock on this locking region for as long as they are connected to the database.  |
｜RWCLIENT(n) | There are a total of 16 RWCLIENT locking regions. After a read-write client connects to the database it attempts to find a free RWCLIENT locking slot to take an EXCLUSIVE lock on. If it cannot find one, this is not an error. If it can, then the lock is held for as long as the read-write client is connected to the database for.<br><br>The sole purpose of these locks is that they allow a read-only client to detect whether or not there exists at least one read-write client connected to the database. Of course if large numbers of read-write clients connect and disconnect from the system in an inconvenient order the system may enter a state where there exists one or more connected read-write clients but none of them hold a RWCLIENT lock. This is not important - if a read-only client fails to detect that the system has read-write clients it may be less efficient, but will not malfunction.|
|WRITER|A database client holds an EXCLUSIVE lock on this locking region while writing data to the database. Outside of recovery, only clients holding this lock may modify the contents of the in-memory b-tree. Holding this lock is synonymous with having an open write transaction on the database.|
|WORKER|A database client holds an EXCLUSIVE lock on this locking region while performing database work (writing data into the body of the database file).|
|CHECKPOINTER|A database client holds an EXCLUSIVE lock on this locking region while performing a checkpoint (syncing the database file and writing to the database header).|
|ROTRANS|A read-only database client holds a SHARED lock on this locking region while reading from a non-live database system.|
|READER(n)|There are a total of 6 READER locking regions. Unless it is a read-only client reading from a non-live database, a client holds a SHARED lock on one of these while it has an open read transaction. Each READER lock is associated with a pair of id values identifying the regions of the in-memory tree and database file that may be read by clients holding such SHARED locks.|

### Database Connect and Disconnect Operations

    