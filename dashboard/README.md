# Heal dashboard

Displays the state of every monitored target: what is reachable, what is
failing, and what looks filtered.

## Running it

```bash
npm install
cp .env.example .env.local     # point at your Heal API
npm run dev                    # http://localhost:3000
```

The API must allow this origin, or the browser blocks every request:

```bash
HEAL_API_CORS_ORIGINS=http://localhost:3000
```

`npm run build` produces the production build, `npm start` serves it,
`npm run lint` checks the source, and `npm run typecheck` runs TypeScript.

## Tests

```bash
npm test          # vitest, once
npm run test:watch
```

The suite covers the pieces where a mistake would misinform an operator: the
status semantics (a suspicion must never be coloured as a confirmed failure),
the global verdict's ordering, the round history rebuilt from InfluxDB, the API
client's envelope handling, and the proxy route. It uses jsdom and stubs
`fetch`, so no API or database is needed.

## Screens

- **Overview** — a headline verdict for the whole network, counts per state, and
  one row per target with its check history and latency trace.
- **Target** — the latest reading from each probe, a latency chart over a
  selectable range and aggregation, and the full round history. "Check now"
  probes immediately instead of waiting for the interval.

## Reading the design

**Colour encodes certainty, not just severity.** Confirmed failures are red.
`suspected_filtered` is violet and drawn as a hollow mark, because Heal reports
filtering as a suspicion and never as a fact — showing it in red would claim
more than the backend does.

**The evidence strip is the signature.** Each bar is one check round, oldest to
newest. Heal only reports filtering after the same suspicious signal appears in
consecutive rounds, so the strip shows that evidence accumulating; a single
spike reads very differently from a run of them. Healthy rounds are drawn short
and failures full height, so the exceptions catch the eye rather than the
baseline.

Per-round history is reconstructed from the InfluxDB series, since MySQL keeps
only the latest verdict.

## Layout

```
src/
├── app/            routes: overview and /sites/[siteId]
├── components/     panels, evidence strip, charts, status marks
└── lib/            api client, types mirroring the backend, formatters
```

`src/lib/types.ts` mirrors `api/schemas/v1` and `api/models/enums.py`; update it
when the API contract changes.
