# SQLite queue
Uses Python sqlite3 and a local database file.
Producer inserts and consumer claims run in transactions.
Committed tasks survive a process restart.
Multiple processes may open the same file; simultaneous writers serialize and may wait for the lock.
For this prototype, processing is at least once: a worker crash can cause redelivery.
No separate database server is required.
