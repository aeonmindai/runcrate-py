# Runcrate Python SDK

Official Python SDK for the [Runcrate](https://runcrate.com) API.

## Installation

```bash
pip install runcrate
```

## Quick Start

```python
from runcrate import Runcrate

client = Runcrate(api_key="rc_live_...")

# List GPU instances
instances = client.instances.list()

# Create an instance
instance = client.instances.create(
    name="training-run",
    ssh_key_id="key_abc123",
    gpu_type="A100",
)

# Check status
status = client.instances.get_status(instance.id)
print(status.status, status.ip)

# Check billing
balance = client.billing.get_balance()
print(f"Credits: ${balance.credits_balance}")

client.close()
```

## Async Usage

```python
import asyncio
from runcrate import AsyncRuncrate

async def main():
    async with AsyncRuncrate(api_key="rc_live_...") as client:
        instances = await client.instances.list()
        balance = await client.billing.get_balance()
        print(f"Running {len(instances)} instances, ${balance.credits_balance} credits")

asyncio.run(main())
```

## Configuration

```python
client = Runcrate(
    api_key="rc_live_...",       # or set RUNCRATE_API_KEY env var
    base_url="https://runcrate.com",  # default
    timeout=30.0,                # request timeout in seconds
    max_retries=3,               # retry on 429/5xx with exponential backoff
)
```

## Resources

### Instances

```python
client.instances.list(search="my-gpu")
client.instances.create(name="run", ssh_key_id="key", gpu_type="A100")
client.instances.get("instance-id")
client.instances.terminate("instance-id")
client.instances.get_status("instance-id")
client.instances.list_types(gpu_type="A100", region="us-east")
```

### Crates

```python
client.crates.list()
client.crates.create(name="jupyter", ssh_key_id="key", gpu_type="A100")
client.crates.get("crate-id")
client.crates.terminate("crate-id")
```

### Projects

```python
client.projects.list()
client.projects.create(name="my-project")
client.projects.get("project-id")
client.projects.update("project-id", name="new-name")
client.projects.delete("project-id")
```

### SSH Keys

```python
client.ssh_keys.list()
client.ssh_keys.create(name="my-key", public_key="ssh-ed25519 AAAA...")
client.ssh_keys.delete("key-id")
```

### Storage

```python
client.storage.list()
client.storage.get("volume-id")
```

### Billing

```python
client.billing.get_balance()
client.billing.list_transactions(limit=10, offset=0)
client.billing.usage(from_date="2025-01-01", to_date="2025-01-31")
```

### Templates

```python
client.templates.list(search="cuda", category="ml", page_size=10)
```

## Error Handling

```python
from runcrate import Runcrate, NotFoundError, InsufficientCreditsError, RateLimitError

client = Runcrate(api_key="rc_live_...")

try:
    instance = client.instances.get("nonexistent")
except NotFoundError as e:
    print(f"Not found: {e.message}")
except InsufficientCreditsError as e:
    print(f"Need more credits: {e.message}")
except RateLimitError as e:
    print(f"Rate limited: {e.message}")
```

## Pagination

```python
# Transactions support offset-based pagination
page = client.billing.list_transactions(limit=10, offset=0)
print(page.data)        # list of Transaction objects
print(page.has_more)    # True if more pages exist
print(page.total)       # total count

# Templates support page-based pagination
templates = client.templates.list(page=1, page_size=25)
```

## Requirements

- Python >= 3.9
- httpx >= 0.25.0
- pydantic >= 2.0
