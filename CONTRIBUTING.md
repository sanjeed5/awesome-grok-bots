# Contributing

## Refresh the marketplace index

```bash
python3 scripts/refresh_marketplace.py
```

This uses only public pages and public endpoints. It writes `data/marketplace.json` and `marketplace/README.md`. Commit both together.

Useful flags:

- `--skip-enrich` to skip the per-template listing API
- `--skip-link-check` to skip HTTP checks
- `--workers N` to change parallelism (default 8)

Do not store pre-signed recipe download URLs.

## Curated picks

The curated section in the root README is not open for additions yet. Once it is, open an issue or pull request with:

- bot name
- share URL (`https://x.ai/bot/...`) or marketplace URL
- the section it belongs in
- one or two sentences on what it does and why it is interesting
- a source post if you found it in public

Verify the link still resolves before sending it. Do not copy descriptions from other awesome lists.
