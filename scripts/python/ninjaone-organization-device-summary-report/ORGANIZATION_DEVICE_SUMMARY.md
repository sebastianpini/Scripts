# NinjaOne Organization Device Summary Report

Reports NinjaOne organization counts for workstations, servers, Apple mobile devices, Android devices, network devices, total devices, end users, ticket totals, and used cloud backup storage.

## Usage
Store NinjaOne credentials in `env/default.env` as described in the repository root README. Then run from the repository root:

```bash
./ninja org-summary
```

For multiple environments, pass the environment name before the script name:

```bash
./ninja demo-eu org-summary
```

## Environment variables
These variables belong in `env/default.env` or another selected `env/*.env` file, not in `~/.zshrc` or copied into the shell before every run.

- `NINJA_ONE_CLIENT_ID` (required): OAuth client ID.
- `NINJA_ONE_CLIENT_SECRET` (required): OAuth client secret.
- `NINJA_ONE_INSTANCE` (optional): NinjaOne instance hostname. Defaults to `eu.ninjarmm.com`.
- `NINJA_ONE_SCOPE` (optional): OAuth scope. Defaults to `monitoring management`.

## Behavior
- Uses `/v2/organizations-detailed` to load organizations.
- Uses `/v2/devices-detailed` to count workstations and servers by organization.
- Uses `/v2/user/end-users` to count end users by organization.
- Tries `/v2/queries/backup/usage`, then `/v2/queries/backup-usage`, to sum used cloud backup storage by organization. If neither endpoint is available, the report continues with `0.00`.
- Uses `/v2/ticketing/trigger/boards`, then `/v2/ticketing/trigger/board/{boardId}/run`, to count deduplicated tickets by organization.
- Counts device classes ending in `_SERVER` as servers.
- Counts device classes ending in `_WORKSTATION`, plus `MAC`, as workstations. Macs are not counted as Apple mobile devices.
- Counts Android mobile devices from Android device class or OS metadata.
- Counts Apple mobile devices from Apple/iOS/iPad/iPhone/iPadOS/tvOS device class metadata or mobile Apple OS metadata. Apple OS manufacturer metadata alone is not counted, because that can also describe Macs.
- Counts network devices from network-oriented device class or role metadata, including markers such as `NETWORK`, `NMS`, `SNMP`, `SWITCH`, `ROUTER`, `FIREWALL`, `ACCESS_POINT`, `WIRELESS`, `WAP`, `PRINTER`, `UPS`, `NAS`, and `SAN`.
- Counts ticket statuses whose parent status is open (`parentId` `2000`) in `OpenTickets`. This supports localized/custom status names such as `Offen` and `Work in progress`.
- Counts ticket statuses whose parent status is resolved or closed (`parentId` `5000` or `6000`) in `ResolvedOrClosedTickets`.
- Counts ticket sources `USER`, `TECHNICIAN`, `EMAIL`, `WEB_FORM`, `HELP_REQUEST`, `END_USER`, and `CONTACT` in `TicketsCreatedByUser`.
- Counts ticket sources `AUTOMATION`, `CONDITION`, `ACTIVITY`, `SCHEDULED_SCRIPT`, `SCRIPT`, `API`, `SYSTEM`, `POLICY`, `MONITOR`, and `WEBHOOK` in `TicketsCreatedByAutomation`.
- Outputs `Name`, `TotalDevices`, `Workstations`, `Servers`, `AppleDevices`, `AndroidDevices`, `NetworkDevices`, `EndUsers`, `TotalTickets`, `OpenTickets`, `ResolvedOrClosedTickets`, `TicketsCreatedByUser`, `TicketsCreatedByAutomation`, and `CloudStorageUsedGB`.

## Example
```text
Name              TotalDevices Workstations Servers AppleDevices AndroidDevices NetworkDevices EndUsers TotalTickets OpenTickets ResolvedOrClosedTickets TicketsCreatedByUser TicketsCreatedByAutomation CloudStorageUsedGB
----------------- ------------ ------------ ------- ------------ -------------- -------------- -------- ------------ ----------- ----------------------- -------------------- -------------------------- ------------------
Example Org       58           42           7       4            2              3              51       32           7           21                      18                   14                         128.45
```

## No Liability / No Warranty
This script is provided as-is, without warranty of any kind, express or implied. Use it at your own risk and validate it in a safe test environment before using it in production. The author and contributors are not liable for any damages, data loss, service disruption, security issue, or other consequence resulting from use, misuse, or inability to use this script.
