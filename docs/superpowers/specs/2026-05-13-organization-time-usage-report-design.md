# Organization Time Usage Report Design

## Goal

Add a separate NinjaOne Organization Time Usage report that shows cumulative ticket time and NinjaOne remote-session duration per organization for a selected calendar period. The ticket total is based on ticket time-entry dates, not ticket creation dates, and outputs cumulative ticket time as decimal hours. Remote-session duration is mapped to organizations through the device's organization and outputs cumulative duration as decimal minutes.

## User Interface

Add a new launcher script name:

```bash
./ninja org-time-usage
./ninja org-time-usage --period this
./ninja org-time-usage --period last
./ninja demo-eu org-time-usage --period last
```

`--period` accepts:

- `last`: the previous complete local calendar month. This is the default.
- `this`: the current local calendar month from the first day of the month through the execution time.

The report prints one table row per organization:

```text
Name        TicketTimeHours RemoteSessionMinutes TimeEntries TicketsWithTime PeriodStart PeriodEnd
Example Org 12.50           87.75                8           5               2026-04-01  2026-04-30
```

`TicketTimeHours` and `RemoteSessionMinutes` are formatted with two decimal places.

## Scope

This is a new report, not an extension of `org-summary`. Existing organization summary behavior remains unchanged.

The first version includes only organization-level totals. Ticket-level, technician-level, device-level, remote-session-level, CSV export, and billable/non-billable breakdowns are out of scope for this design.

## Architecture

Create a new Python report under `scripts/python/ninjaone-organization-time-usage-report/`, following the existing Python report style:

- Use the shared NinjaOne OAuth and JSON helper from `scripts/python/_shared/ninja_api.py`.
- Keep CLI parsing, period calculation, API loading, normalization, aggregation, and table rendering as small dedicated functions.
- Add the new report to the root `ninja` launcher as `org-time-usage`.
- Add documentation next to the script and update the repository script indexes.

The report should load organizations through `/v2/organizations-detailed` so organizations with zero ticket time or zero remote-session duration in the period still appear with `0.00`.

The report should also load devices through `/v2/devices-detailed` to build a `deviceId -> organizationId` lookup. Remote sessions are assigned to organizations by looking up the organization of the device involved in the session.

Ticket time-entry retrieval is isolated behind a dedicated loader function. The rest of the report works only with normalized time-entry records:

- organization id
- ticket id
- entry timestamp
- duration in hours

If the NinjaOne API returns organization ids directly on time entries, the report uses them. If entries only contain ticket ids, the report resolves organization ownership through ticket data before aggregation.

Remote-session retrieval is isolated behind a dedicated loader function. The rest of the report works only with normalized remote-session records:

- device id
- session timestamp
- duration in minutes

## Period Handling

Period calculations use the local system timezone:

- `last`: start is local midnight on the first day of the previous month; end is local midnight on the first day of the current month.
- `this`: start is local midnight on the first day of the current month; end is the execution timestamp.

Time-entry and remote-session filtering both use an inclusive start and exclusive end:

```text
entryDate >= period_start
entryDate < period_end
sessionTimestamp >= period_start
sessionTimestamp < period_end
```

The table displays `PeriodStart` and `PeriodEnd` as local dates. For `this`, `PeriodEnd` displays the local execution date.

## Aggregation

Each organization summary tracks both ticket time totals and remote-session totals.

For each valid time entry in the selected period:

1. Normalize the organization id.
2. Normalize the ticket id when present.
3. Normalize the duration into decimal hours.
4. Add the duration to that organization's `TicketTimeHours`.
5. Increment `TimeEntries`.
6. Add the ticket id to an organization-local set for `TicketsWithTime`.

Entries without a usable organization mapping, date, or duration are skipped and counted for a final warning.

For each valid remote session in the selected period:

1. Normalize the device id.
2. Resolve the organization id through the device lookup.
3. Normalize the session duration into decimal minutes.
4. Add the duration to that organization's `RemoteSessionMinutes`.

Remote sessions without a usable device mapping, date, or duration are skipped and counted for a final warning.

## Duration Normalization

The normalizer accepts common API shapes without spreading API-specific logic through the aggregation code:

- decimal hours fields such as `hours`, `durationHours`, or `timeSpentHours`
- minute fields such as `minutes`, `durationMinutes`, or `timeSpentMinutes`
- second fields such as `seconds`, `durationSeconds`, or `timeSpentSeconds`
- millisecond fields such as `milliseconds` or `durationMilliseconds`

Numeric strings are accepted. Empty, non-numeric, negative, or missing duration values are invalid and cause that entry to be skipped.

Remote-session durations are normalized to decimal minutes. The normalizer accepts common fields such as `minutes`, `durationMinutes`, `seconds`, `durationSeconds`, `milliseconds`, and `durationMilliseconds`.

## Error Handling

OAuth or organization loading failures abort the report with exit code `1`, matching the existing report behavior.

Time-entry and remote-session loading failures also abort with exit code `1`. These values are the primary metrics for this report, so silently returning `0.00` for every organization would be misleading.

The report prints a clear `stderr` message when:

- time entries cannot be queried
- remote sessions cannot be queried
- an entry is skipped because required fields are missing or invalid
- an entry or remote session cannot be mapped to an organization

Skipped-entry and skipped-session warnings are aggregated so normal report output remains readable.

## Testing

Add focused unit tests for:

- `this` and `last` period calculation, including month boundaries
- duration normalization for hours, minutes, seconds, milliseconds, and numeric strings
- aggregation per organization
- ticket de-duplication for `TicketsWithTime`
- remote-session aggregation through `deviceId -> organizationId`
- skipped invalid entries
- table rows for organizations with zero ticket time and zero remote-session duration

Extend the launcher test so `org-time-usage` resolves to the new report script and still supports explicit environment selection.

## Documentation

Add a report document next to the script with:

- usage examples
- environment variables inherited from the shared NinjaOne setup
- period semantics
- output column descriptions
- no-liability/no-warranty notice consistent with the existing docs

Update the root `README.md` and `scripts/README.md` so customers can discover the new report.
