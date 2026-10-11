# Product context

## Why it exists

Teaching material for data hackathons (students, Madrid). The original version (archived at tag
`v1-archive`) produced data but its buses ran empty ("zombie apocalypse"): stop queues lived in
two services that never exchanged riders, some terminals were lost to a float comparison and first
stops were never served. It also relied on Timestream, closed to new customers since June 2025.

## Who uses it and how

| Who | Uses | Through |
|---|---|---|
| Participants (12 groups by default) | live state, history, SQL | MQTT, HTTP API, MCP, Parquet, web map |
| Organisers | deploy, generate history, hand out keys, check answers | Makefile, GitHub Actions, `private/scenario.json` |

Participants get one key per group and the guide `docs/participantes.md` (Spanish). The answer
key (the generated scenario) is only in the private part of the data bucket.

## Experience goals

- Data that *looks* like a city: rush hours, weekends, summer, school terms, holidays, events
  near real venues, one chronically overloaded line, disruptions.
- Narratives are discoverable only from data: dates, venues, intensities and the overloaded line
  are drawn from a fresh secret seed each generation.
- Easy start: curl examples, Python examples, Swagger/AsyncAPI page on the site, MCP config.
- Cheap and short-lived: ~$5-15 for the event day; budgets alert early.
