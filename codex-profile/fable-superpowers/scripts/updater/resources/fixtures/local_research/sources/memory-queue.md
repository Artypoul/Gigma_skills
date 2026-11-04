# In-memory queue
Uses Python queue.Queue.
Queue state is held only in RAM and is lost on process exit.
The queue synchronizes threads in one process; it does not coordinate separate producer processes.
No persistence or external dependencies.
