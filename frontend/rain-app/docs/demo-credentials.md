# RAIN — demo sign-in

**These are not secrets.** Every credential below ships inside the client-side
bundle (`src/config/access.ts`). They stop a link being casually forwarded into
the demo; they protect nothing.

Locally, `<host>` is `http://localhost:5550`.

| Door | URL | Username | Password |
|---|---|---|---|
| RAIN (default landing page) | `<host>/login/rain` | `rain` | `rain@9705` |
| Platform picker (lists RAIN only) | `<host>/login/ultra` | `ultra` | `ultra@9705` |

Direct link that skips the form: `<host>/login/rain/?access=rain@9705`.

`/`, `/login` and any unknown `/login/<slug>` go to `/login/rain`. Signing out
returns to the same door. Sessions are per browser tab.
