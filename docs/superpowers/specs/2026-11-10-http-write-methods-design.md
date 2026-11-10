# Fixed HTTP write methods

Scope: extend the existing fixed HTTP JSON ToolSource with explicit `PUT` and
`PATCH`, plus strict boolean `allow_empty_204=False`. This is a tool integration
increment, not framework parity or a new execution authority.

POST, PUT and PATCH send the existing canonical UTF-8 JSON body; only GET accepts
query mappings. No dynamic URLs, methods, headers, redirects, automatic retries,
DELETE or inferred write policies. Every source still requires an explicit
ToolDescriptor and ToolPolicy. Output Schema validation applies to JSON null too.

Only opt-in HTTP 204 with an empty observed body can return `None`. Nonzero
Content-Length or Transfer-Encoding on 204 is refused. Empty 200, whitespace,
invalid JSON, compressed and oversized responses retain their original rejection.
The option is strict bool, pinned in identity only when true. Existing default
POST/GET identities and legacy transport invocation arguments stay unchanged;
this is a selected metadata compatibility promise, not arbitrary old History or
private-method fingerprint compatibility.

The original thread trackers own actual client/handler completion. Waiting
cancellation and retryable close must not release real work early. Test actual
loopback HTTP, original Local approval/reopen/duplicate commands, lost response
and reconciliation, and cancellation followed by close retry. Temporal transport
configuration remains available through its existing factory; no new real
Temporal service qualification is claimed by this batch.

Verification: source and checkout-external installed targeted regressions, wheel
and sdist integrity, runtime-only installed smoke, original POST/GET metadata and
dispatch compatibility, Ruff/format/diff. Preserve all original packages and
failures, and unrelated website edits. No new full framework/platform/model
qualification; report the selected checks explicitly.
