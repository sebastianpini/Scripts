# NinjaOne Device Owner Assignment

Assigns every NinjaOne device to one technician owner. The script skips devices
already assigned to the target owner.

The NinjaOne API endpoint used for the write is:

```text
POST /v2/device/{id}/owner/{ownerUid}
```

NinjaOne documents this endpoint as requiring the `management` scope and a
delegated OAuth token. For that reason, this script uses Authorization Code Flow
instead of client credentials.

## Setup

Create or update your environment file:

```bash
cp env/example.env env/default.env
```

Set these values:

```bash
NINJA_ONE_INSTANCE=eu.ninjarmm.com
NINJA_ONE_CLIENT_ID=
NINJA_ONE_CLIENT_SECRET=
NINJA_ONE_SCOPE="monitoring management"
NINJA_ONE_AUTH_CODE_SCOPE="monitoring management offline_access"
NINJA_ONE_REDIRECT_URI=http://localhost:8080/
```

In NinjaOne, the API application must have:

- `Management` scope
- Authorization Code grant type
- Refresh Token grant type
- Redirect URI matching `NINJA_ONE_REDIRECT_URI`

`offline_access` is included in `NINJA_ONE_AUTH_CODE_SCOPE` so NinjaOne can
return a refresh token. Keep `NINJA_ONE_SCOPE` at `monitoring management` for
the existing client-credentials reports.

## Token Cache

The script stores delegated OAuth tokens locally in:

```text
.do_not_push/ninjaone-device-owner-token-cache.json
```

That folder is gitignored. Treat this file like a password because the
refresh token can mint new access tokens until it expires or is revoked.

The logic is intentionally kept in the `Delegated OAuth token cache` section
of `assign_owner.py`:

1. If the cached access token is still valid, reuse it.
2. If the access token expired and a refresh token is cached, call
   `/ws/oauth/token` with `grant_type=refresh_token`.
3. Save the refreshed response back to the cache.
4. If NinjaOne returns a new refresh token, replace the old one. This is the
   sliding/rotating refresh-token pattern. If no new refresh token is returned,
   keep the previous refresh token.
5. Fall back to browser login only when the cache is missing, invalid, expired
   without a refresh token, or rejected by NinjaOne.

Cache controls:

```bash
python ninja.py owner-devices --reset-token-cache
python ninja.py owner-devices --no-token-cache
python ninja.py owner-devices --token-cache .do_not_push/custom-token-cache.json
```

## Usage

Dry run first:

```bash
python ninja.py owner-devices
```

Apply the changes:

```bash
python ninja.py owner-devices --apply
```

By default, the owner lookup is by technician name:

```text
Sebastian Pini
```

You can be more explicit:

```bash
python ninja.py owner-devices --owner-email sebastian@example.com
python ninja.py owner-devices --owner-uid 00000000-0000-0000-0000-000000000000
```

If your registered redirect URI is not localhost, capture the `code` from the
redirect URL manually and pass it in:

```bash
python ninja.py owner-devices --auth-code CODE_FROM_REDIRECT_URL
```

For native app registrations, use PKCE:

```bash
python ninja.py owner-devices --pkce
```
