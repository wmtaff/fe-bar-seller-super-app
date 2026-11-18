# Evidence 04: GenAI call insights (`ai_query`)

Task 5. Job task `ai_call_insights` (sql_task on warehouse `${var.warehouse_id}`, file
`src/ai/call_insights.sql`, after `governance_comments_tags`). It builds `gold_call_insights` from
`silver_transcripts` with `ai_query('databricks-claude-sonnet-5-5', ...)`. Collected 2026-11-18.

## Runs

| Run | Job run id | Task result | Task duration | MERGE source rows | Inserted | Updated |
|---|---|---|---|---|---|---|
| 1: first full run, table created by the task | 618050339207062 | SUCCESS | 553 s (about 9.2 min) | 640 | 640 | 0 |
| 2: re-run, nothing changed | 727734322158833 | SUCCESS | 9 s | 0 | 0 | 0 |
| 3: re-run after planting an orphan row `orphan-check-t5` | 567648393440609 | SUCCESS | 9 s | 0 | 0 | 0 |

Run 3 checks the R17 orphan delete. Before the run, a row with meeting_id `orphan-check-t5` (not in
silver_transcripts) was inserted by hand. Table history: v7 WRITE (the planted row), v9 DELETE
`numDeletedRows=1`, v10 MERGE `numSourceRows=0`. Afterwards there were 0 orphan rows and 640 rows total.
The staging table `tmp_call_insights_batch` is dropped at the end of every run (`SHOW TABLES LIKE
'tmp_call_insights*'` is empty).

Each transcript is sent to the model once. Run 1 made 640 `ai_query` calls in one batched CTAS (no
per-row Python loop). Re-runs send only new, changed (`transcript_sha256`), re-prompted
(`prompt_version`/`model`) or previously failed rows.

## Counts (after run 3)

| transcripts | insight_rows | with_summary | errors | coverage_pct |
|---|---|---|---|---|
| 640 | 640 | 640 | 0 | 100.0 |

| with_competitor | with_next_steps | with_dated_step | avg_next_steps |
|---|---|---|---|
| 257 | 640 | 640 | 3.06 |

- **Error count: 0** (`extract_error IS NOT NULL`). Coverage is 100.0% of
  silver_transcripts (the test needs at least 95%).
- Jordan Rivera, found by name through gold_user_hierarchy and gold_opportunity_pipeline.owner_id:
  **17 insight rows on 11 opportunities** (the test needs at least 8).
- Sentiment: neutral 336, positive 285, negative 19.
- Competitors mentioned (calls): FleetCore 97, Trackwell 96, RoadLynx 94.
  Only the three fictional competitors appear.
- Interests (calls): Vehicle Telematics 480, Fuel & Maintenance 336, Driver Safety 295, AI Dash Cams 286, Equipment Monitoring 90, Compliance/ELD 67. All values are
  on the product list.

## Table properties

- `delta.enableChangeDataFeed = true` (set at create and re-asserted every run), for the Lakebase sync.
- Informational `PRIMARY KEY (meeting_id)`. Table COMMENT plus a COMMENT on every column (Genie).
- No PII. The prompt uses the attendee roster's name, role and company only. Raw attendee emails are
  never read (`.email` never appears in the SQL, enforced by a unit test), and an integration test
  finds no email-shaped strings in any insight field. So there is no `contains_pii` tag.

## Structured output: deviation from the brief

The brief asks for `responseFormat => <insights_schema.json>`. The endpoint rejects it, verified live:

```
responseFormat json_schema -> errorMessage: "INVALID_PARAMETER_VALUE: Structured output is not supported
  for this model because its translation requires forced tool use, which newer Anthropic models reject."
responseFormat {"type":"json_object"} -> same error
modelParameters temperature -> "The model does not support the parameter(s): temperature."
```

So `src/ai/insights_schema.json` is embedded verbatim in the prompt (a unit test checks this), and the
reply is validated in SQL. `try_parse_json` flags invalid JSON, `from_json` casts the reply to the
declared struct, enums are filtered (interests, sentiment, stance), and `due` is kept only when it
is a YYYY-MM-DD date. `src/ai/parse.py` applies the same rules in Python. `failOnError => false` is
kept, and `.errorMessage` goes into `extract_error`. `max_tokens` is 8000: at 2000, some replies were
cut off mid-JSON with no errorMessage, apparently because the budget includes the model's reasoning
tokens.

## Prompt (prompt_version v1)

The `ai_query` call, verbatim from `src/ai/call_insights.sql`. The long single-line literal after
"conforms to this JSON Schema" is the compact form of `insights_schema.json`, shown pretty-printed below.

```sql
ai_query(
      'databricks-claude-sonnet-5-5',
      concat(
        'You are a sales operations analyst at Fleetwise, a fleet telematics vendor. ',
        'Read the Google Meet sales call transcript below and extract insights for the Fleetwise seller.\n\n',
        'Context\n',
        '- Meeting date: ', date_format(p.started_at, 'EEEE, yyyy-MM-dd'), '\n',
        '- Fleetwise seller (opportunity owner): ', coalesce(p.owner_name, 'unknown'), '\n',
        '- Customer account: ', coalesce(p.account_name, 'unknown'), '\n',
        '- Attendees (name | role | company): ', coalesce(array_join(p.roster, ' / '), 'unknown'), '\n\n',
        'Return ONLY one JSON object, with no prose and no markdown code fences, that conforms to this JSON Schema:\n',
        '{"type":"object","additionalProperties":false,"required":["summary","next_steps","open_items","interests","competitors","objections","sentiment","stakeholders"],"properties":{"summary":{"type":"string"},"next_steps":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["action","owner","due"],"properties":{"action":{"type":"string"},"owner":{"type":"string"},"due":{"type":["string","null"]}}}},"open_items":{"type":"array","items":{"type":"string"}},"interests":{"type":"array","items":{"type":"string","enum":["Vehicle Telematics","AI Dash Cams","Driver Safety","Fuel & Maintenance","Compliance/ELD","Equipment Monitoring"]}},"competitors":{"type":"array","items":{"type":"string"}},"objections":{"type":"array","items":{"type":"string"}},"sentiment":{"type":"string","enum":["positive","neutral","negative"]},"stakeholders":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["name","role","stance"],"properties":{"name":{"type":"string"},"role":{"type":"string"},"stance":{"type":"string","enum":["champion","supportive","neutral","skeptical","blocker"]}}}}}}',
        '\n\nField rules\n',
        '- summary: exactly 2 or 3 sentences (at most 70 words) of plain prose for a busy seller: where the deal stands, the main customer concern or blocker, and the agreed next step. No lists, no dates beyond the key next step.\n',
        '- next_steps: every concrete follow-up that someone committed to on the call, on either side. ',
        'action: an imperative phrase naming the deliverable, specific enough to act on (for example "Send the revised proposal with 20-vehicle pilot pricing"). ',
        'owner: the person who committed, written as "Full Name (role)" using the attendee roster, for example "Alex Kim (Fleetwise AE)" or "Sam Ortiz (customer, IT Director)". Use the role alone if no name is known. ',
        'due: the date stated for that step as YYYY-MM-DD, resolved against the meeting date (for example "by Monday" means the first Monday after the meeting). Null when no timing was stated. ',
        'Do not invent steps that were not agreed.\n',
        '- open_items: at most 5 questions, requests or decisions still unresolved at the end of the call, most important first, each a short phrase. Do not repeat the next steps.\n',
        '- interests: Fleetwise products the customer asked about or showed interest in, using only these exact names: ',
        'Vehicle Telematics (GPS, live location, trip history), AI Dash Cams (cameras, video, event clips), ',
        'Driver Safety (coaching, scorecards, safe driving), Fuel & Maintenance (fuel spend, idling, fault codes, preventive maintenance), ',
        'Compliance/ELD (ELD, hours of service, roadside inspections, FMCSA), Equipment Monitoring (trailers, generators, unpowered assets). Empty if none.\n',
        '- competitors: competing vendors mentioned on the call, company names only, exactly as spoken. Fleetwise is never a competitor. Empty if none.\n',
        '- objections: at most 5 customer concerns or pushback, each a short phrase (price, timing, contract terms, driver or union pushback on cameras, IT or security review, adoption). ',
        'When a competitor quote is mentioned, include the competitor, price and expiry as YYYY-MM-DD, for example "RoadLynx quoted $28 per vehicle per month, valid through 2026-12-04".\n',
        '- sentiment: the overall customer attitude toward buying from Fleetwise on this call: positive, neutral or negative.\n',
        '- stakeholders: customer-side people (never Fleetwise employees) who spoke or were named, with role = their title or function from the roster or the conversation ("unknown" if not known), ',
        'and stance toward the deal = champion (actively pushing it internally), supportive, neutral, skeptical, or blocker (opposing it). Never include email addresses or phone numbers.\n\n',
        'Transcript\n',
        p.transcript_text
      ),
      modelParameters => named_struct('max_tokens', 8000),
      failOnError => false
    )
```

JSON Schema (`src/ai/insights_schema.json`):

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": [
    "summary",
    "next_steps",
    "open_items",
    "interests",
    "competitors",
    "objections",
    "sentiment",
    "stakeholders"
  ],
  "properties": {
    "summary": {
      "type": "string"
    },
    "next_steps": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "action",
          "owner",
          "due"
        ],
        "properties": {
          "action": {
            "type": "string"
          },
          "owner": {
            "type": "string"
          },
          "due": {
            "type": [
              "string",
              "null"
            ]
          }
        }
      }
    },
    "open_items": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "interests": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": [
          "Vehicle Telematics",
          "AI Dash Cams",
          "Driver Safety",
          "Fuel & Maintenance",
          "Compliance/ELD",
          "Equipment Monitoring"
        ]
      }
    },
    "competitors": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "objections": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "sentiment": {
      "type": "string",
      "enum": [
        "positive",
        "neutral",
        "negative"
      ]
    },
    "stakeholders": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "name",
          "role",
          "stance"
        ],
        "properties": {
          "name": {
            "type": "string"
          },
          "role": {
            "type": "string"
          },
          "stance": {
            "type": "string",
            "enum": [
              "champion",
              "supportive",
              "neutral",
              "skeptical",
              "blocker"
            ]
          }
        }
      }
    }
  }
}
```

## Sample rows (full, from gold_call_insights)

### 1. Jordan Rivera's opportunity (a call with a competitor mention)

```json
{
  "meeting_id": "osy-hieh-jmy",
  "opportunity_id": "0060g000000037gAAA",
  "account_id": "0010g0000000008AAA",
  "started_at": "2026-11-16T12:18:00.000Z",
  "summary": "Elm Crossing is lukewarm on the proposal. Laura Martin finds the price higher than expected and doubts the first-year payback, and Carolyn Kim cites a reorg and FleetCore hardware failures. Jordan will send a FleetCore side-by-side comparison and Carolyn will set up time with leadership, both by 2026-11-23.",
  "next_steps": [
    {
      "action": "Send a side-by-side comparison of Fleetwise against FleetCore",
      "owner": "Jordan Rivera (Fleetwise AE)",
      "due": "2026-11-23"
    },
    {
      "action": "Set up a meeting with the leadership team to review the proposal",
      "owner": "Carolyn Kim (customer, Fleet Manager)",
      "due": "2026-11-23"
    }
  ],
  "open_items": [
    "Whether payback occurs within the first year",
    "Whether to start with all 157 vehicles or a pilot",
    "Rollout timing given the reorg",
    "Leadership team approval",
    "Pricing relative to Trackwell"
  ],
  "interests": [
    "Compliance/ELD",
    "Vehicle Telematics",
    "Fuel & Maintenance",
    "AI Dash Cams"
  ],
  "competitors": [
    "FleetCore",
    "Trackwell"
  ],
  "objections": [
    "Price higher than expected (about $2,355 per month list for 157 vehicles)",
    "Doubts it pays for itself in the first year",
    "Timing is poor due to the reorg",
    "Rollout would need to be very slow",
    "Trackwell is cheaper on paper"
  ],
  "sentiment": "neutral",
  "stakeholders": [
    {
      "name": "Laura Martin",
      "role": "CFO",
      "stance": "skeptical"
    },
    {
      "name": "Carolyn Kim",
      "role": "Fleet Manager",
      "stance": "neutral"
    }
  ],
  "model": "databricks-claude-sonnet-5-5",
  "prompt_version": "v1",
  "extracted_at": "2026-11-18T19:50:57.837Z"
}
```

### 2. Another seller, positive call, no competitor

```json
{
  "meeting_id": "ahb-qfkw-jye",
  "opportunity_id": "0060g00000003DTAAY",
  "account_id": "0010g00000000ZHAAY",
  "started_at": "2026-09-03T19:00:00.000Z",
  "summary": "Lone Pine Civil Group (about 553 vehicles) has approved budget and wants to replace patchy GPS and spreadsheets, driven by stolen excavators and rising fuel costs. Main concerns are ERP integration, the union position on in-cab cameras, and change fatigue after a bad rollout. Aaron will send the order form by 2026-09-07, and Ashley will check the union agreement by 2026-09-09.",
  "next_steps": [
    {
      "action": "Send the order form",
      "owner": "Aaron Daniels (Fleetwise AE)",
      "due": "2026-09-07"
    },
    {
      "action": "Check the union agreement for restrictions on in-cab cameras",
      "owner": "Ashley Fox (customer, IT)",
      "due": "2026-09-09"
    }
  ],
  "open_items": [
    "Fleetwise contact to start the security review",
    "ERP integration fit, with a solutions engineer session for IT",
    "Reference call with a similar customer",
    "Whether the CFO must sign off despite budget being approved",
    "Monthly executive report sample, offered after a pilot"
  ],
  "interests": [
    "Vehicle Telematics",
    "Equipment Monitoring",
    "Fuel & Maintenance",
    "AI Dash Cams"
  ],
  "competitors": [],
  "objections": [
    "Change fatigue after a painful rollout with the last vendor",
    "Union agreement may restrict in-cab cameras",
    "ERP integration must be understood before Patricia can take it upstairs",
    "Security review required",
    "Leadership needs comfort, including a reference call and CFO sign-off"
  ],
  "sentiment": "positive",
  "stakeholders": [
    {
      "name": "Ashley Fox",
      "role": "IT",
      "stance": "supportive"
    },
    {
      "name": "Patricia Schmitt",
      "role": "VP Operations",
      "stance": "neutral"
    },
    {
      "name": "Willie Cook",
      "role": "Safety Director",
      "stance": "supportive"
    }
  ],
  "model": "databricks-claude-sonnet-5-5",
  "prompt_version": "v1",
  "extracted_at": "2026-11-18T19:50:57.837Z"
}
```

### 3. Negative call (renewal at risk)

```json
{
  "meeting_id": "aba-kjnj-qim",
  "opportunity_id": "0060g00000003GlAAI",
  "account_id": "0010g00000000AxAAI",
  "started_at": "2026-11-10T16:45:00.000Z",
  "summary": "The renewal is at risk. Adoption is spotty, some veteran drivers see the system as Big Brother, and IT doubts it pays back in year one and wants to wait until next fiscal year. Jeffery is noncommittal and will take the ROI model to Thursday's leadership meeting. Mike will send the revised proposal by 2026-11-17.",
  "next_steps": [
    {
      "action": "Send the revised proposal",
      "owner": "Mike Oliver (Fleetwise AE)",
      "due": "2026-11-17"
    },
    {
      "action": "Present the ROI model at the leadership meeting",
      "owner": "Jeffery Hoover (customer, VP Operations)",
      "due": "2026-11-12"
    }
  ],
  "open_items": [
    "Whether the solution pays for itself in year one",
    "ERP integration approach and a solutions engineer session with IT",
    "Renew now or defer to next fiscal year",
    "Plan to fix spotty field adoption and driver pushback",
    "Monthly leadership reporting and business case for budget"
  ],
  "interests": [
    "Vehicle Telematics",
    "Driver Safety"
  ],
  "competitors": [],
  "objections": [
    "Must pay for itself in the first year; ROI not convinced",
    "Spotty field adoption, with a couple of sites no longer using it",
    "Veteran drivers see it as Big Brother",
    "ERP integration unclear, which blocks IT from escalating",
    "Likely to wait until next fiscal year"
  ],
  "sentiment": "negative",
  "stakeholders": [
    {
      "name": "Jeffery Hoover",
      "role": "VP Operations",
      "stance": "neutral"
    },
    {
      "name": "Austin Ferguson",
      "role": "IT",
      "stance": "skeptical"
    }
  ],
  "model": "databricks-claude-sonnet-5-5",
  "prompt_version": "v1",
  "extracted_at": "2026-11-18T19:50:57.837Z"
}
```

## Tests

- `tests/unit/test_parse.py`: 10 passed (normalizer, including `test_parse_valid`,
  `test_parse_insights_handles_invalid_json` and `test_interests_filtered_to_products`).
- `tests/unit/test_call_insights_sql.py`: 7 passed (job wiring, schema embedded, enums, failOnError,
  MERGE/orphan delete/CDF, no emails, column comments).
- `tests/integration/test_insights.py`: 8 passed against the live table (coverage at least 95%,
  Jordan at least 8, one row per meeting with no orphans, a summary or an error on every row, enums,
  owned next steps, no emails, CDF and comments).
