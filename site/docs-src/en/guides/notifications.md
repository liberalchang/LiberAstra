---
title: Notifications
---

# Notifications

Settings → Notifications pushes task completion, failures, cancellation, and progress to Telegram, Feishu, DingTalk, Bark, or a Webhook. The first version is single-user: every channel and rule belongs to the current account (the administrator).

Notifications are asynchronous. A finished job writes a delivery to the outbox; a background worker sends it. Failed sends retry per channel and never change the job result.

## Quick start

1. Under General, choose the push language. Add a public base URL if you want links in messages.
2. Under Channels, create a channel, fill in its address/key, save, then click Test.
3. Under Rules, create a rule and select events and channels. Success and failure are on by default; turn on Progress if you want digests.
4. Run a job and check Delivery log.

## General

| Setting | Purpose | How to fill |
|---------|---------|-------------|
| Push language | Language for every notification message | Chinese or English. Global, independent of the UI language. Pending/sent messages are not re-rendered |
| Outbound proxy | Send notification requests through a proxy, often for Telegram | For example `http://127.0.0.1:7890`. Empty uses `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY`. Only http/https; no credentials or SOCKS5 |
| Public base URL | Base for job/canvas links in messages | For example `http://10.0.0.2:8000` or your domain. Empty means no links |

Proxy notes:

- An explicit global proxy applies to every channel. `NO_PROXY` may not apply when a proxy is set explicitly.
- If Telegram needs a proxy but a LAN webhook needs a direct connection, turn off “Use global proxy” on that channel. Each channel only chooses whether to use the global proxy; it cannot have its own proxy URL.
- TLS certificates are verified by default. Self-signed HTTPS on a LAN is not supported yet; use HTTP or a trusted certificate.

## Channels

Common fields:

| Field | Purpose | Default / range |
|-------|---------|-----------------|
| Name | Display name; unique within the account | Required |
| Type | Telegram / Feishu / DingTalk / Bark / Webhook | Cannot change after creation; create a new channel to switch |
| Enabled | Disabled channels create no new deliveries; queued deliveries are skipped | On |
| Max attempts | How many times a failed send is tried | 3, range 1–10 |
| Backoff base | Base for exponential retry delay, capped at 1 hour | 30 seconds |
| Timeout | Per-request HTTP timeout | 10 seconds, range 1–60 |
| Use global proxy | Whether this channel uses the global proxy from General | On by default; when off, the channel connects directly and ignores environment proxies |

Secret fields (Bot Token, webhook secret, Bark Device Key, HMAC secret) are encrypted and shown only as a suffix or host. While editing, these fields and URLs containing tokens show only masks (for example `****ABCD` or `https://host/***`); saving an empty field keeps the current value. The Bark server URL is not a secret and is filled in fully. Feishu/DingTalk/Webhook optional secrets can be removed with “Clear optional secrets”.

### Telegram

| Field | Purpose | How to get it |
|-------|---------|---------------|
| Bot Token | Bot credential | BotFather gives “numeric bot ID + colon + secret”, for example `123456789:AAE...`. The colon is in the middle; do not add a leading colon, and do not paste only the part after the colon |
| Chat ID | Where messages go | This is the destination chat ID, **not the bot ID**. Click the search icon inside the field to fetch it automatically, or use `@userinfobot` for your numeric user ID and send `/start` to the bot first. Groups/channels are usually negative `-100...` |
| Parse mode | Message formatting | HTML or MarkdownV2; HTML by default |
| Disable link preview | Do not expand link cards | On by default |

Save and click Test. The bot must already be in the target group, or you must have messaged it first.

**Fetch Chat ID automatically**: click the search icon inside Chat ID. The app reads the bot's recent incoming messages with the current Bot Token:

- A new channel uses the Token currently typed in the form; when editing and the Token field is empty, the saved Token is used.
- One candidate fills the field directly. Multiple candidates are listed as private chats, groups, and channels; click one to fill it.
- The bot must have received a message first: send `/start` in a private chat, or add the bot to a group/channel and post a message. Channels require administrator access.
- Only unconfirmed recent updates (usually within 24 hours) are read; messages are not consumed or deleted. If the bot uses a webhook, `getUpdates` conflicts and the webhook must be disabled first.
- When no chat is found, the field is not changed and the page asks you to message the bot first.

### Feishu

| Field | Purpose | How to get it |
|-------|---------|---------------|
| Webhook URL | Group custom-bot URL | Feishu group → Settings → Group bots → Add custom bot → copy the webhook |
| Signing secret (optional) | Required when signature verification is enabled | Same settings page as the webhook |

### DingTalk

| Field | Purpose | How to get it |
|-------|---------|---------------|
| Webhook URL | Group custom-bot URL | DingTalk group → Group settings → Smart group assistant → Add bot → Custom → copy the webhook |
| Signing secret (optional) | Required when signing is enabled | Same settings page as the webhook |
| Mention phones | @ specific people | Comma-separated, for example `13800000000,13900000000` |
| Mention everyone | @ all members | Off by default; the group may restrict it |

### Bark

| Field | Purpose | Default |
|-------|---------|---------|
| Server URL | Bark server | `https://api.day.app` |
| Device Key | Device push key | Required |
| Group (optional) | iOS notification group | Empty |
| Sound (optional) | Notification sound | Empty |

### Webhook

| Field | Purpose | Notes |
|-------|---------|-------|
| Webhook URL | Receiver URL | http/https only; POST only in the first version |
| Custom headers | Extra request headers | JSON object, for example `{"X-Token":"..."}`. Reserved headers such as `Host` and `Content-Length` are ignored |
| HMAC secret (optional) | Sign requests | Adds `X-LiberAstra-Signature: sha256=...`, `X-LiberAstra-Timestamp`, and `X-LiberAstra-Delivery` |
| Body template (optional) | Custom JSON body | Placeholders: `{title}` `{body}` `{event}` `{job_id}` `{link}` `{delivery_id}`. The rendered result must be a JSON object |

Without a body template, the default payload is:

```json
{
  "event": "job.succeeded",
  "title": "Job title",
  "body": "Message body",
  "job": {"id": "job-id"},
  "link": "http://example/jobs/job-id",
  "timestamp": "2026-11-10T12:00:00+00:00"
}
```

Receivers can use `X-LiberAstra-Delivery` for idempotent deduplication.

## Rules

| Setting | Purpose | Notes |
|---------|---------|-------|
| Name | Rule display name; unique within the account | Required |
| Enabled | Disabled rules create no new deliveries; queued deliveries are skipped | Re-enabling does not backfill jobs from the disabled period |
| Events | Which job states trigger notifications | Succeeded, failed, canceled, progress. Succeeded/failed are on by default; progress is off |
| Progress interval | How often to build a progress digest | Minimum 60 seconds, default 900. To disable progress, uncheck Progress |
| Max jobs per digest | How many jobs one digest lists | Default 10, range 1–50; extra jobs show as “N more” |
| Job kind filter | Notify only specific job kinds | Comma-separated, for example `video.motion, canvas.run`. Empty means all, but canvas child jobs are skipped by default |
| Channels | Where the rule delivers | At least one |
| Quiet hours | Suppress progress digests during a time window | Only progress is suppressed; completion/failure/cancel still send |
| Quiet start/end | Window boundaries | Start-inclusive, end-exclusive; overnight windows are supported |
| Time zone | IANA time zone for quiet hours | For example `Asia/Shanghai`; Windows needs tzdata |
| Include output links | Add a job link to completion/failure/cancel messages | Requires a public base URL; empty means no link |
| Advanced: template overrides | Custom success/failure/progress text | Empty uses the default template |

### Job kind filter

Rules are cross-channel: one rule can select Telegram and Bark at the same time. The channel list is grouped by type, but it does not hide other types based on the rule name or current selection. Create separate rules when each channel needs different events or intervals.

- Empty means all top-level jobs.
- Every function node on a canvas is a separate `canvas.node` job. By default these are not sent per node; the whole run sends one `canvas.run` summary.
- To debug per-node notifications, list `canvas.node` explicitly.
- To receive only one kind, for example motion transfer, enter `video.motion`.

### Template placeholders

Success/failure templates:

- `{job_name}`: job title
- `{status}`: status
- `{progress}`: progress percentage
- `{elapsed}`: elapsed time
- `{error}`: redacted error summary
- `{link}`: job link
- `{outputs}`: output count

Progress template:

- `{count}`: number of jobs in this digest
- `{running}`: running count
- `{queued}`: queued count
- `{jobs}`: default per-job list
- `{link}`: Jobs page link

### Progress and quiet hours

- No active jobs means no digest.
- Each rule creates at most one digest per interval bucket.
- Canvas progress is grouped into one line instead of one line per node.
- Quiet hours only affect progress; completed, failed, and canceled jobs still notify.

## Delivery log

The Delivery log shows the latest 100 deliveries:

| Status | Meaning |
|--------|---------|
| `pending` | Queued |
| `sending` | Being sent |
| `sent` | Sent |
| `failed` | Retries exhausted, or a non-retryable 4xx |
| `skipped` | Rule/channel deleted or disabled, among other reasons |

Filter by status. `failed` / `skipped` deliveries can be retried while the target still exists. Deliveries are kept for 30 days; only terminal records are cleaned up.

## Canvas and batches

- A canvas run creates one synthetic `canvas.run` summary job and sends one completion/failure/cancel message by default.
- The summary job is hidden from the Jobs list and cannot be canceled or retried.
- Batch jobs currently notify per job. Use the job kind filter if that is too noisy; batch-level summaries come later.

## Troubleshooting

**The test message does not arrive.** Check the Bot Token / Chat ID / webhook, whether the bot is in the group, whether Feishu/DingTalk signing is enabled, and whether the proxy is reachable. Telegram usually needs a proxy in mainland China.

**Jobs finish but no notification arrives.** Check: rule enabled, event selected, channel enabled, job kind filter, quiet hours (progress only), and public base URL (links only). Canvas nodes are not sent per node by default.

**Telegram returns 404 Not Found.** Usually the Bot Token is malformed or revoked: a complete token must contain the numeric bot ID, one colon, and the secret; do not put the colon first, and do not paste only the part after the colon.

**The Chat ID is the bot ID.** The number before the colon in the Bot Token is the bot's own ID, not a chat ID. Use your user ID, or the negative ID of a group/channel. Telegram returns 403 "bot can't send messages to the bot" when you use the bot ID.

**Fetch Chat ID finds no chats.** Make sure the bot has received a message in the target chat: send `/start` in a private chat, or add the bot to a group/channel and post a message. A new, unsaved channel can fetch with the typed Token; when editing, an empty Token field uses the saved Token.

**Duplicate messages.** Delivery is at-least-once: a request may have succeeded while its response was lost, so a retry can duplicate it. Webhook receivers can deduplicate with `X-LiberAstra-Delivery`.

**Are 4xx responses retried?** No, except 408/429. For 429, `Retry-After` is honored up to 1 hour.

**I changed a secret but it did not take effect.** Leaving a secret empty keeps the old value. Enter a new value to replace it. Feishu/DingTalk/Webhook optional secrets can be removed with “Clear optional secrets”.

**Self-signed HTTPS.** Certificates are verified by default; there is no per-channel disable switch in the first version. Use HTTP or a trusted certificate.

**Time zone does not work.** Use an IANA name; the Windows installer needs tzdata. An invalid zone fails validation and is not silently accepted.

## Security

- Channel secrets are encrypted with Fernet; the API only returns masks. Logs and error summaries are redacted.
- API Tokens behave as administrator credentials; do not give them to untrusted agents.
- Webhook URLs must be http/https and cross-host redirects are not followed. In the first version they are configured by the administrator.

Related: [Settings](/en/guides/settings); [Works & Tasks](/en/guides/works); [Canvas & Director](/en/guides/canvas).
