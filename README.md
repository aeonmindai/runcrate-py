# Runcrate Python SDK

Official Python SDK for the [Runcrate](https://runcrate.ai) API.

## Installation

```bash
pip install runcrate-sdk
```

## Quick Start

```python
from runcrate import Runcrate

client = Runcrate(api_key="rc_live_...")

# Chat completion
response = client.models.chat_completion(
    model="meta-llama/Meta-Llama-3.1-8B-Instruct",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)

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
        response = await client.models.chat_completion(
            model="meta-llama/Meta-Llama-3.1-8B-Instruct",
            messages=[{"role": "user", "content": "Hello!"}],
        )
        print(response.choices[0].message.content)

asyncio.run(main())
```

## Configuration

```python
client = Runcrate(
    api_key="rc_live_...",                        # or set RUNCRATE_API_KEY env var
    base_url="https://runcrate.ai",               # infra API (default)
    inference_url="https://api.runcrate.ai",      # model inference API (default)
    timeout=30.0,                                 # request timeout in seconds
    max_retries=3,                                # retry on 429/5xx with exponential backoff
)
```

## Model Inference

The `client.models` resource connects to `api.runcrate.ai` for AI model inference. Same API key works for both infrastructure and inference.

### Chat Completions

```python
# Standard request
response = client.models.chat_completion(
    model="meta-llama/Meta-Llama-3.1-8B-Instruct",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Explain quantum computing in 3 sentences."},
    ],
    max_tokens=256,
    temperature=0.7,
)
print(response.choices[0].message.content)
print(f"Tokens used: {response.usage.total_tokens}")

# Streaming
for chunk in client.models.chat_completion(
    model="meta-llama/Meta-Llama-3.1-8B-Instruct",
    messages=[{"role": "user", "content": "Write a poem about GPUs"}],
    stream=True,
):
    delta = chunk.get("choices", [{}])[0].get("delta", {})
    print(delta.get("content", ""), end="", flush=True)
```

### Image Generation

```python
result = client.models.generate_image(
    model="black-forest-labs/FLUX.1-schnell",
    prompt="A futuristic city skyline at sunset",
    width=1024,
    height=1024,
)
# result.data[0].b64_json contains the base64-encoded image
```

### Video Generation

```python
# Submit video job (async processing)
job = client.models.generate_video(
    model="google/veo-3.0",
    prompt="A drone flyover of a mountain landscape",
    duration=8,
)
print(f"Job ID: {job.id}, Status: {job.status}")

# Poll until complete
import time
while True:
    job = client.models.get_video_status(job.id)
    print(f"Status: {job.status}")
    if job.status in ("completed", "failed"):
        break
    time.sleep(5)

# Download the video
if job.status == "completed":
    video_bytes = client.models.download_video(job.id)
    with open("output.mp4", "wb") as f:
        f.write(video_bytes)
```

### Text-to-Speech

```python
audio_bytes = client.models.text_to_speech(
    model="openai/tts-1",
    input="Hello, welcome to Runcrate!",
    voice="alloy",
    response_format="mp3",
)
with open("speech.mp3", "wb") as f:
    f.write(audio_bytes)
```

### Transcription (Speech-to-Text)

```python
with open("audio.wav", "rb") as f:
    result = client.models.transcribe(
        model="openai/whisper-1",
        file=f,
        filename="audio.wav",
    )
print(result.text)
print(f"Duration: {result.duration}s")
```

## Infrastructure Resources

### Instances

```python
client.instances.list(search="my-gpu")
client.instances.create(name="run", ssh_key_id="key", gpu_type="A100")
client.instances.get("instance-id")
client.instances.terminate("instance-id")
client.instances.get_status("instance-id")
client.instances.list_types(gpu_type="A100", region="us-east")
```

### Schedules

Start an instance or a job later: once at a time (`run_at`), or on a recurring 5-field `cron` read in an IANA `timezone`. A schedule starts within about 2 minutes of its time, as you, in the environment it was created in. `spec` is the create body of that kind and must set `max_runtime_minutes`.

```python
from datetime import datetime
from zoneinfo import ZoneInfo

# Every night at 02:00 London time
nightly = client.schedules.create(
    kind="job",
    cron="0 2 * * *",
    timezone="Europe/London",
    name="nightly-train",
    spec={"command": "python train.py", "gpu_type": "H100", "max_runtime_minutes": 120},
)
print(nightly.next_run_at)

# Once, tomorrow morning. run_at must carry a timezone: a naive datetime raises ValueError.
client.schedules.create(
    kind="instance",
    run_at=datetime(2026, 10, 21, 9, 0, tzinfo=ZoneInfo("Europe/London")),
    spec={"name": "eval-box", "gpu_type": "A100", "ssh_key_id": "key_abc123", "max_runtime_minutes": 60},
)

client.schedules.list()
client.schedules.get(nightly.id)
client.schedules.update(nightly.id, enabled=False)        # pause
client.schedules.update(nightly.id, enabled=True)         # resume from the next occurrence
client.schedules.update(nightly.id, cron="0 3 * * 1-5")   # retime
run = client.schedules.run_now(nightly.id)                # launch now; run.job or run.instance
client.schedules.delete(nightly.id)
```

Recurring runs must be at least 15 minutes apart, `run_at` can be up to 365 days ahead, and you can have at most 50 schedules per environment and 200 per workspace. `overlap="skip"` (the default) skips a run while the previous one is still live; `overlap="allow"` starts it anyway. `run_now` raises `InsufficientCreditsError` with `code == "BUDGET_REACHED"` when the environment's monthly budget is spent.

Each run launches as `schedule.run_as`, the person who created the schedule or last changed its spec or timing or resumed it, using the same kind of sign-in (`run_as_credential`: `"user"`, `"api_key"` or `"agent"`). If that API key is revoked or the agent sign-in ends, the schedule pauses with `last_status == "credential_revoked"`. Resume it to run as you.

### Environments

```python
client.environments.list()
client.environments.create(name="staging")
client.environments.get("env-id")
client.environments.update("env-id", name="production")
client.environments.delete("env-id")
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
