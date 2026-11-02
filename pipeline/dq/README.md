# Data quality rules

Generated automatically by the engine from the other configs (no YAML needed):

| Layer  | Rule                                   | From                                   |
|--------|----------------------------------------|----------------------------------------|
| landing| file present, header matches config    | `sources/*.yaml` columns               |
| bronze | row count > 0, primary key unique, NOT NULL columns, date parse failures | `sources/*.yaml` |
| silver | primary key unique, foreign keys resolve | `silver/*.yaml` primary_key / foreign_keys |
| silver | MCDS JSON Schema conformance per entity | `silver/*.yaml` mcds block            |

Custom rules live in `<layer>.yaml`: a SQL query returning the number of violating rows (0 = pass).
`severity: fail` stops the pipeline; `warn` is reported only. Views available: `bronze.<table>`,
`silver.<entity>`, `gold.<report>`, crosswalk views `xw_<name>`; `${rules...}` tokens are resolved.
