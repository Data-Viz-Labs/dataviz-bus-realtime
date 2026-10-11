# Project brief

## Goal

A data playground for a short (2-hour, Friday afternoon) data hackathon: a **real-time
simulation of Madrid's EMT bus network** with **1-3 years of synthetic history** that hides
stories participants must discover from the data alone.

## Core requirements

1. **Realistic, consistent simulation**: real EMT lines, stops and fleet sizes (official GTFS);
   buses actually carry people; passengers are conserved; every stop is served.
2. **Real time** for participants: MQTT on AWS IoT Core (one key per group) and a live web map.
3. **History** for participants: hourly tables per line and stop for years, raw stop calls and
   bus positions for the last days; queryable through an HTTP API (REST + SQL + Parquet
   downloads) and an MCP server for AI agents.
4. **Hidden narratives**: per-line loads (centre busier), one overloaded peripheral line
   (90-100 %, peaks 120 %), Madrid's calendar and random events (snowstorm, football, concerts,
   festival, Pride, bullfights...). Dates/places random per generation; reading the code must not
   reveal when things happened.
5. **AWS-native and cheap**: lives about one day (deploy the day before, backfill, run the event,
   shut down). Budgets with email alerts. Amazon Location for routes, maps, tracking.
6. **Documented surfaces**: OpenAPI, AsyncAPI, MCP tool docs, data dictionary, participants' guide.
7. **Operable**: Terraform for infra, GitHub Actions for software deploys, a Makefile runbook.

## Out of scope

Production hardening, multi-day operation, SLAs, real EMT live data.

## Repository

`github.com/Data-Viz-Labs/dataviz-bus-realtime` (default branch `main`). MIT licence; network data
© EMT Madrid (open data terms).
