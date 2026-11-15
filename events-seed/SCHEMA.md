---
title: "Events space schema"
---

# Events space

Personal events, same page schema as the OpenHeidelberg Events space (event-calendar-main).
One page per event under private/ (tier members = private). Frontmatter is the only machine-readable carrier.

Required: uid (immutable, maik-YYYY-MM-DD-slug@events.local), title, event_kind (event | presentation | recommendation),
publish_state (published | cancelled), tier, start_utc and end_utc (quoted YYYY-MM-DDTHH:MM:SSZ),
start_local and end_local (quoted RFC 3339 with offset), timezone (Europe/Berlin), all_day (boolean),
location (string, TBD allowed, never empty), organizer, tags (including kind/event).
Optional: series_uid, rrule, occurrence_of, external_url, source_doc, agenda.

The local time must denote the same instant as the UTC time. Berlin is +01:00 in winter and +02:00 in summer.
Body text is the description.
