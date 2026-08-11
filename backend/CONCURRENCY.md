# Concurrency notes — blocking code on the event loop

> Why three bugs existed, how they were found, and how to not write them again.
> Written after auditing all four Python services.

---

## The bug class

`await` checks **one** thing: *is this awaitable?* It never checks *does this
actually yield?*

So blocking code inside an `async def` is a **silent bug**. No error, no
warning, correct-looking code. All three bugs below read fine on review.

> `async def` is a **promise** to yield at slow points. It is not a mechanism.
> Nothing enforces it. If the body calls sync code, the promise is broken.

---

## Why it is catastrophic, not just slow

The event loop is **not a thread**. It is a `while True:` running *on* the main
thread:

```python
while True:
    ready = ask_the_os_which_sockets_have_data()
    for callback in ready:
        callback()          # runs Python until it hits an await
```

When code calls something slow, the main thread goes **into** that call and the
loop sits one frame below, unable to reach its next iteration:

```
main thread:
  while True:                        <- the event loop, stuck here
    └─ login()
        └─ verify_password()
            └─ bcrypt.checkpw()
                └─ [300ms]           <- thread is HERE
```

Nothing gets served. Not other logins — not search, not listings, not the
`/health` probe that Kubernetes uses to decide whether to kill the pod.

asyncio is **cooperative**. It cannot preempt a task. It can only be *given*
control back. Blocking code never gives it back.

---

## Why the GIL does not save us

The GIL is **per process** (so one per pod), and it only gates Python
**bytecode**.

`bcrypt` 5.x is Rust-backed and drops the GIL while hashing. That helped
nothing, because **releasing a lock only helps threads that are waiting for
it**:

- The main thread was not waiting for the GIL. It was trapped *inside* bcrypt.
  Handing it the lock just means it does more bcrypt.
- The ~40 idle anyio threadpool threads were not waiting either. They were
  waiting for *work*, and nothing was ever dispatched to them.

> **The GIL decides WHEN a thread runs. The call stack decides WHAT it runs.**

---

## What the fix actually does

`run_in_threadpool` does **not** make the blocking function yield. It stays
100% blocking forever.

The **wrapper** is the awaitable. It hands the function to a worker thread and
returns a Future. `await` on that Future bottoms out in a real `yield` — in
`asyncio/futures.py`:

```python
def __await__(self):
    if not self.done():
        self._asyncio_future_blocking = True
        yield self          # <- every await in the entire system funnels here
    return self.result()
```

So the blocking did not disappear. **It moved somewhere nobody is waiting on
it.**

The coroutine is not forgotten — it is **parked**. The loop registers a
callback on the Future and walks away with the ticket. The worker calls
`set_result()`, the callback fires, and the coroutine resumes on the exact next
line with all its locals intact.

---

## What we win

| | Outcome |
|---|---|
| **Always** | The loop is free. Other requests get served. **This is the point.** |
| **Bonus** | True parallelism — but only if the offloaded code releases the GIL *and* a core is free. bcrypt (Rust) and socket waits both qualify. |
| **Never** | More throughput. 2 vCPUs is 2 vCPUs. |

Pure Python offloaded to a thread gives **concurrency only** — the two threads
take 5ms turns via GIL handoff. Still worth doing: it is the difference between
the health check passing and Kubernetes restarting the pod.

> This is about **blast radius**, not speed.

---

## How to spot the next one

- **Assume a library blocks** unless it advertises async. Anything predating
  ~2016 does — `requests`, `psycopg2`, and most vendor SDKs (Resend, Stripe,
  boto3) still ship sync-only clients.
- Inside an `async def`, **every slow line needs `await`** on something
  async-native. A bare call to something slow is the tell.
- **Some libraries ship both — check the import.** `redis` vs `redis.asyncio`.
  `httpx.Client` vs `httpx.AsyncClient`. Those were correct here; the three
  below were not.
- **Do not wrap fast things (<10ms).** The thread dispatch costs more than it
  saves. This is why `create_access_token` was correctly left alone.

---

## Audit results

**Fixed (were blocking):**

| File | Call |
|---|---|
| `app/services/email_service.py` | `resend.Emails.send()` — unbounded network wait |
| `app/routers/users.py` | `verify_password()` — ~300ms bcrypt |
| `app/database/transactions.py` | `get_password_hash()` — ~300ms bcrypt |

**Verified clean:**

- `asyncpg`, `redis.asyncio`, `httpx.AsyncClient`, `aiokafka`, `temporalio` —
  all async-native, safe to await directly
- **image-service** — already wraps every MinIO call, PIL processing, and NSFW
  inference in `run_in_threadpool`
- **consumer** and **temporal-worker** — fully async, activities only log
- `SQLAlchemy` / `psycopg2` — declarations and Alembic only, never in the
  request path. Blocking is fine there; migrations run offline in an
  initContainer where there is no loop to block.

**Future trap:** `app/temporal/activities/send_email_activity.py` is a mock
whose comment says to swap in `resend.Emails.send()` for production. Wrap it
when you do, or the email bug reappears inside the Temporal worker.