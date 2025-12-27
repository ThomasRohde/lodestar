# Lease Mechanics

Leases are time-limited claims that prevent multiple agents from working on the same task.

## How Leases Work

When you claim a task, you get a **lease** with:

- A unique lease ID
- An expiration time (default: 15 minutes)
- Association with your agent ID

```bash
$ lodestar task claim F001
Claimed task F001
  Lease: L1234ABCD
  Expires in: 15m
```

## Lease Expiry

Leases are checked at read time, not by a background daemon:

1. When listing claimable tasks, expired leases are filtered out
2. When attempting to claim, existing expired leases don't block
3. When renewing, only non-expired leases can be extended

This means:

- No background process needed
- System is stateless between CLI invocations
- Multiple agents can run on different machines

## Renewing Leases

If your work takes longer than expected:

```bash
lodestar task renew F001
```

This extends the lease by another TTL period from the current time.

## Releasing Leases

If you need to stop working without completing:

```bash
lodestar task release F001
```

This immediately frees the task for others to claim.

## Atomicity

Lease operations are atomic using SQLite transactions:

1. Check if task has an active (non-expired) lease
2. If not, create new lease
3. Commit transaction

This prevents race conditions when multiple agents try to claim the same task.

## Configuration

Default TTL is 15 minutes. Override per-claim:

```bash
lodestar task claim F001 --ttl 30m
```

Or set a default in your environment:

```bash
export LODESTAR_LEASE_TTL=30m
```
