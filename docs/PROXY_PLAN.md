# Future proxy and API gateway plan

This is a plan for adding `repos/proxy` **when there is a concrete need for it**.
The current request path already has a proxy: Vite forwards `/api` to Banse in
development, and the [deployment runbook](DEPLOYMENT.md) puts Caddy in front of
the built UI and Banse in production. Keep that arrangement until one of the
triggers below applies.

## When to add it

Add an application-level proxy if the browser needs one stable API that combines
multiple backend services, if a backend-for-frontend must reshape or aggregate
responses, or if server-side handling of user sessions or third-party secrets is
required. Decide which of these requirements it serves before implementing it.

If the need is only HTTPS, routing, response headers, or access logging, extend
Caddy's existing configuration. If the need is only authorization for Banse
resources, start with FastAPI dependencies in Banse. A new repo adds another
network hop and service to deploy, monitor, and update; it is not a security
boundary by itself.

## Target request path

```text
Browser -- HTTPS --> Caddy -- /api/* --> proxy (private loopback port)
                       |                         |
                       +-- static UI             +--> Banse (private loopback port)
                                                    --> other services, if added

Banse --> read-only DuckDB
ingestion --> DuckDB during a coordinated import window
```

The browser should continue to call relative `/api/...` URLs. Caddy remains the
public entry point and serves the UI. Banse and the new proxy must be unreachable
from the public network; on the single-VM deployment, bind both to `127.0.0.1`
and expose only ports 80/443. The proxy must not access DuckDB directly. It
calls Banse, which remains the owner of basketball query behavior and response
models.

## Implementation phases

1. **Define the contract.** List the routes that need proxy behavior. For each,
   record its upstream, allowed methods, authentication requirement, timeout,
   and whether the response is passed through or transformed. Preserve existing
   `/api` paths and response shapes unless a versioned API change is deliberate.
   Choose a session or identity provider only when authentication is actually
   required; specify which component verifies identity and which enforces each
   permission. Do not treat CORS or an unverified forwarded header as identity.

2. **Create `repos/proxy`.** Use a small Python ASGI service if application
   behavior is needed; FastAPI keeps its tooling consistent with Banse. Give it
   its own `pyproject.toml`, `src/proxy/`, tests, and README. Put route handlers
   and upstream client code in separate modules. Configure the Banse origin,
   timeouts, and any secrets through environment variables, with local defaults
   for development. Keep credentials out of Git and logs.

3. **Implement explicit forwarding.** Map only approved `/api` routes to Banse;
   do not create an unrestricted URL forwarding endpoint. Forward required path
   parameters and query strings, preserve relevant status codes, and handle
   upstream timeouts and failures predictably. Add request IDs to logs and
   responses. Apply authentication or request aggregation only where the route
   contract calls for it. Keep any cache policy explicit, especially for
   user-specific responses.

4. **Switch local development.** Start Banse, proxy, and Vite from the root Make
   launcher. Change Vite's `/api` target from Banse to the proxy. Keep the UI's
   relative `/api` calls unchanged. Add an integration check that exercises a
   browser-facing request through Vite and proxy to Banse.

5. **Deploy privately, then switch Caddy.** Run the proxy as its own `systemd`
   service on a loopback port, check its health and a real tournament query, and
   only then change Caddy's `/api/*` upstream from Banse to the proxy. Preserve
   the URI and query string so Banse routes continue to work. Keep Banse bound
   to loopback. Deploy Caddy's validated config and check the public UI and API.
   [Caddy's reverse proxy documentation](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
   describes its default URI-preserving behavior.

6. **Verify security and operations.** Test missing, malformed, and unauthorized
   requests; expected 404s; upstream outages; timeouts; and sensitive-header
   handling. Confirm Banse and proxy ports are not publicly reachable. Add
   service logs, error-rate and latency monitoring, and an alert for a failed
   proxy service. Document the new start, update, and recovery commands in the
   [deployment runbook](DEPLOYMENT.md).

## Cutover and rollback

Before cutover, compare representative `/api/tournaments`, overview, player,
team, and game responses through Banse and the proxy. After changing Caddy,
check those routes from the public domain and navigate the UI. If the proxy
fails, restore Caddy's `/api/*` upstream to Banse and reload Caddy; keep Banse
running throughout the cutover. Any newly protected routes need an explicit
rollback decision so reverting routing does not accidentally bypass the new
access policy.

The proxy can be added without changing DuckDB or the ingestion workflow. Docker
is optional; on the initial single VM, a separate `systemd` unit is sufficient.
If the requirement is delegated authentication rather than API composition,
evaluate Caddy's [forward authentication](https://caddyserver.com/docs/caddyfile/directives/forward_auth)
before building a custom service. For route-level permissions within Banse,
FastAPI's [dependency system](https://fastapi.tiangolo.com/tutorial/dependencies/)
is the existing integration point.
