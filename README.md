# Awesome Grok Bots

A complete index of every template on the official [x.ai Grok Bot marketplace](https://x.ai/bot/marketplace), plus a hand-picked list of community bots grouped by role. Open a link, then add the bot to get your own editable copy.

## Contents

- [Curated picks](#curated-picks)
- [Full marketplace index](#full-marketplace-index)
- [Contributing](#contributing)
- [License](#license)
- [Related lists](#related-lists)

## Curated picks

Hand-picked bots that go beyond a raw catalog listing, grouped by the job they do. This section is coming soon. It will mix official marketplace templates with community shares chosen for a clear result, a clever routine, or an unusual use.

### Engineering

Coming soon.

### Sales

Coming soon.

### Marketing

Coming soon.

### Design

Coming soon.

### Product

Coming soon.

### Operations

Coming soon.

### Support and success

Coming soon.

### Finance

Coming soon.

### Recruiting and people

Coming soon.

### Personal and life

Coming soon.

### Content

Coming soon.

### Research

Coming soon.

## Full marketplace index

The official marketplace is indexed in [`marketplace/README.md`](marketplace/README.md), grouped the same way the catalog is: Featured, From Grok Bot Team, Engineering, Sales, Marketing, Design, Personal, Recruiting and People, Product, and Operations.

Machine-readable data is in [`data/marketplace.json`](data/marketplace.json). Refresh both with:

```bash
python3 scripts/refresh_marketplace.py
```

The script reads the public marketplace page, optionally enriches each template from the public listing endpoint, checks that the catalog and share URLs still resolve, and drops entries whose pages are dead.

This index covers the official marketplace only, not the much larger set of public share pages people publish on their own.

## Contributing

- Official marketplace updates: run `python3 scripts/refresh_marketplace.py` and send a pull request with the refreshed `data/marketplace.json` and `marketplace/README.md`.
- Curated picks: please wait until the first list is published, then open an issue or pull request with the bot name, share or marketplace URL, the section it belongs in, and a short note on why it is interesting. Do not add a pick that you have not used or verified.
- Keep entries factual. Do not copy another list's wording. Do not include secrets, private share links, or pre-signed download URLs.

## License

[CC0 1.0 Universal](LICENSE). You can copy, modify, and distribute this list with no restrictions.

## Related lists

Other public indexes exist, including [RongleCat/awesome-grok-bot](https://github.com/RongleCat/awesome-grok-bot), [majiayu000/awesome-grok-bot](https://github.com/majiayu000/awesome-grok-bot), [Maimuzamilhu/awesome-grok-bot-templates](https://github.com/Maimuzamilhu/awesome-grok-bot-templates), [Anil-matcha/awesome-grok-bot](https://github.com/Anil-matcha/awesome-grok-bot), and [tiankonglan/awesome-grok-bot-template](https://github.com/tiankonglan/awesome-grok-bot-template). This repo is a complete official marketplace dump plus (soon) a smaller, sectioned, hand-picked list. It is not a copy of those catalogs.
