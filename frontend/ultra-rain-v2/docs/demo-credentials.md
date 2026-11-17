# Ultra for RAIN — demo sign-in

## Read this first

**This is not a secret, and it is not authentication.** This build is a
scripted prototype with no backend. The credential below ships inside the
client-side bundle, so anyone who can load the page can read it —
`src/config/access.ts` says so at the top of the file, and this document says so
here. It does **not** keep any data away from anybody: all of it is in the same
bundle.

What it buys is that a URL cannot be casually forwarded into a live demo. Treat
it as a courtesy, not as a control.

---

## The door

Replace `<host>` with wherever the app is running (locally,
`http://localhost:5550`).

| | |
|---|---|
| **URL** | `<host>/login/rain` |
| **Username** | `rain` |
| **Password** | `rain@9705` |

`<host>/`, `<host>/login` and any unrecognised `/login/<slug>` redirect here
when signed out. Usernames are matched case-insensitively and surrounding
spaces are ignored; passwords are case-sensitive.

This build serves one tenant. There is no platform door and no market picker;
the multi-tenant platform this was cut from has both, and neither is here.

### Direct link

`<host>/login/rain/?access=rain@9705` skips the form and lands on the
briefing. The token is the client's own password; the link works on the
sign-in door only.

### Bypass link

`<host>/?access=rdvr@9705` skips the sign-in form on any route. The token is
stripped from the URL on arrival, and the grant lasts for that browser tab only.
Override the token at build time with `VITE_POC_ACCESS_KEY` (see
`.env.example`).

### The patient view

`<host>/patient` is Linda's phone-framed view (Ask AI for patients, in
English and Spanish). It sits inside the session but outside the app shell,
so it needs the same sign-in; picking Linda in the persona switcher lands
there too.

---

## Behaviour worth knowing

- **Scope is per browser tab.** It lives in `sessionStorage` under
  `rain_session`, so a refresh keeps you signed in — which matters mid-demo —
  but closing the tab does not leave the machine unlocked.
- **Signing out returns to `/login/rain`.**
- **A stale session from the multi-tenant app is tolerated.** A tab carrying the
  old `'true'` or `'ultra'` scope value is mapped onto this tenant rather than
  being thrown out. Running on port 5550 also keeps the two apps' storage
  separate, since browser storage is scoped by origin, which includes the port.
- **The persona switcher is not gated.** Any of the seven personas is
  reachable from the top-right dropdown, or by `?persona=<id>` on any route.
