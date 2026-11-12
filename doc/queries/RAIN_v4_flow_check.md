# RAIN v0.4: write-back flow, end to end

Run against `http://localhost:8003` by `scripts/e2e/flow_check_v4.py`. Each action writes rows in `rain_v4.synthetic` (and one `synthetic.flow_event` with its undo); the values in the last column are read back from `GET /api/v4/ui/data`, which computes them from those rows on the next request.

| Action | Call | HTTP | What the UI data shows next (before → after) | Check |
|---|---|---|---|---|
| Linda sends her home reading | `POST /api/v4/flow/reading` | 200 | CARE.controlled: 18 → 19; LINDA.readingRecorded: False → True | PASS |
| Brandon books Patricia Jackson into S2 | `POST /api/v4/flow/book` | 200 | CARE.booked: 62 → 63; CARE.brandonBookings: 23 → 22; open slots: 5 → 4; reminders: 15 → 16 | PASS |
| Ana Martin replies C | `POST /api/v4/flow/reply` | 200 | CARE.brandonUnconfirmed: 9 → 8 | PASS |
| Teresa reaches Irene Rivera | `POST /api/v4/flow/contact` | 200 | CARE.brandonBookings: 22 → 23 | PASS |
| Raj signs off the candidate model | `POST /api/v4/flow/signoff` | 200 |  | PASS |
| Dr. Castellanos co-signs: the candidate is released | `POST /api/v4/flow/signoff` | 200 | MODEL.version: v1.3 → v1.4 | PASS |

Flow events logged before the reset: 6. `POST /api/v4/flow/reset` undid 6 events (20 steps); every value checked is back to the start: **yes**.

Result: **PASS**
