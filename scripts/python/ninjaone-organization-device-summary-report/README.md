# NinjaOne Organization Device Summary Report

Reports NinjaOne organization counts for workstations, servers, Apple mobile devices, Android devices, network devices, total devices, end users, and used cloud backup storage.

## Usage
```bash
export NINJA_ONE_INSTANCE="eu.ninjarmm.com"
export NINJA_ONE_CLIENT_ID="your-client-id"
export NINJA_ONE_CLIENT_SECRET="your-client-secret"
python3 ./organization_device_summary_report.py
```

## Environment variables
- `NINJA_ONE_CLIENT_ID` (required): OAuth client ID.
- `NINJA_ONE_CLIENT_SECRET` (required): OAuth client secret.
- `NINJA_ONE_INSTANCE` (optional): NinjaOne instance hostname. Defaults to `eu.ninjarmm.com`.
- `NINJA_ONE_SCOPE` (optional): OAuth scope. Defaults to `monitoring management`.

## Behavior
- Uses `/v2/organizations-detailed` to load organizations.
- Uses `/v2/devices-detailed` to count workstations and servers by organization.
- Uses `/v2/user/end-users` to count end users by organization.
- Tries `/v2/queries/backup/usage`, then `/v2/queries/backup-usage`, to sum used cloud backup storage by organization. If neither endpoint is available, the report continues with `0.00`.
- Counts device classes ending in `_SERVER` as servers.
- Counts device classes ending in `_WORKSTATION`, plus `MAC`, as workstations. Macs are not counted as Apple mobile devices.
- Counts Android mobile devices from Android device class or OS metadata.
- Counts Apple mobile devices from Apple/iOS/iPad/iPhone/iPadOS/tvOS device class metadata or mobile Apple OS metadata. Apple OS manufacturer metadata alone is not counted, because that can also describe Macs.
- Counts network devices from network-oriented device class or role metadata, including markers such as `NETWORK`, `NMS`, `SNMP`, `SWITCH`, `ROUTER`, `FIREWALL`, `ACCESS_POINT`, `WIRELESS`, `WAP`, `PRINTER`, `UPS`, `NAS`, and `SAN`.
- Outputs `Name`, `TotalDevices`, `Workstations`, `Servers`, `AppleDevices`, `AndroidDevices`, `NetworkDevices`, `EndUsers`, and `CloudStorageUsedGB`.

## Example
```text
Name              TotalDevices Workstations Servers AppleDevices AndroidDevices NetworkDevices EndUsers CloudStorageUsedGB
----------------- ------------ ------------ ------- ------------ -------------- -------------- -------- ------------------
Example Org       58           42           7       4            2              3              51       128.45
```

## No Liability / No Warranty
This script is provided as-is, without warranty of any kind, express or implied. Use it at your own risk and validate it in a safe test environment before using it in production. The author and contributors are not liable for any damages, data loss, service disruption, security issue, or other consequence resulting from use, misuse, or inability to use this script.
