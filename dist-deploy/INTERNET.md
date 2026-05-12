# Storymaster — Cloudflare Tunnel deploy

Public hostname → Cloudflare edge (TLS) → cloudflared (TrueNAS) →
nginx (TrueNAS) → Rocky VM:8765 → Storymaster container.

## What's in this bundle for the public deploy

- `storymaster-web.tar.gz` — the image (build it on the dev box, ship it).
- `docker-compose.yml` — runs the container on Rocky, exposes port 8765
  on the LAN.
- `.env.example` — runtime config; secure cookies are on by default.
- `truenas-nginx.conf` — the server block for nginx on TrueNAS.
- `cloudflared-ingress.yml` — the tunnel ingress rule for the
  cloudflared on TrueNAS.

## Order of operations

1. **Pick a public hostname** that's already inside one of your
   Cloudflare zones (e.g. `storymaster.example.com`). No new DNS record
   needed for tunnel ingress — Cloudflare creates it implicitly.

2. **Bring up the container on Rocky** (see `INSTALL.md`):

   ```sh
   cd /opt/storymaster
   docker load < storymaster-web.tar.gz
   cp .env.example .env
   vim .env                                    # set DB URL, SYNC_SECRET_KEY
   chmod 600 .env
   mkdir -p backups
   docker compose up -d
   docker compose exec app python -m storymaster.api.scripts.create_admin --username alice
   ```

3. **Lock the Rocky firewall** so 8765 is reachable only from the
   TrueNAS box. Replace `<TRUENAS_LAN_IP>` with that IP:

   ```sh
   # Open 8765 only to the TrueNAS box.
   sudo firewall-cmd --permanent \
       --add-rich-rule='rule family="ipv4" source address="<TRUENAS_LAN_IP>" port port="8765" protocol="tcp" accept'
   # Make sure no other rule allows 8765 to the world.
   sudo firewall-cmd --permanent --remove-port=8765/tcp 2>/dev/null || true
   sudo firewall-cmd --reload
   ```

   Quick sanity from the TrueNAS box:

   ```sh
   curl -fsS http://<rocky-lan-ip>:8765/api/health
   # → {"status":"ok",...,"database_connected":true,...}
   ```

   And from a third machine on the LAN — should fail (connection refused
   or timeout):

   ```sh
   curl --max-time 3 http://<rocky-lan-ip>:8765/api/health
   ```

4. **Add the nginx server block on TrueNAS.**

   Copy `truenas-nginx.conf` to `/etc/nginx/conf.d/storymaster.conf` (or
   wherever your TrueNAS nginx loads conf snippets), edit the upstream
   address (`192.168.x.y:8765` → your Rocky VM's LAN IP), and reload:

   ```sh
   sudo nginx -t                          # config syntax check
   sudo systemctl reload nginx
   ```

   Don't forget the rate-limit zone in the `http {}` block (the comment
   at the bottom of `truenas-nginx.conf` shows the one-liner). nginx
   refuses to start if the zone is referenced but not defined.

5. **Add the cloudflared ingress rule.**

   Edit your existing tunnel config (typically
   `~/.cloudflared/config.yml` or `/etc/cloudflared/config.yml`),
   adding the rule from `cloudflared-ingress.yml` *before* the catch-all
   `http_status:404` line.

   ```sh
   sudo systemctl restart cloudflared
   ```

   Verify cloudflared picked up the new ingress:

   ```sh
   cloudflared tunnel list                # should show your tunnel as healthy
   ```

   On the Cloudflare dashboard, the hostname should now appear under the
   tunnel's Public Hostnames list. If it doesn't, the config wasn't
   read — check `journalctl -u cloudflared` for parse errors.

6. **Test the round-trip.**

   ```sh
   curl -fsS https://storymaster.example.com/api/health
   # → {"status":"ok",...}
   ```

   Then open the hostname in a browser and log in as the admin user you
   created in step 2. The session cookie should be marked `Secure` (you
   can verify in browser devtools → Application → Cookies).

## Hardening worth knowing about

These are reasonable for a "standard sensitivity" deploy but worth
calling out:

- **Login rate-limit**: the `truenas-nginx.conf` includes a `limit_req`
  on `/api/auth/login` (10 req/s sustained, 20 burst per source IP).
  Tune in the nginx `http {}` block.
- **Password strength**: `create_admin` accepts any non-empty password.
  No lockout on repeated failures. The Argon2 hash makes brute-force
  expensive but not impossible.
- **Cookie secure flag**: on by default (`STORYMASTER_SECURE_COOKIES=true`
  in the deploy env). The `Secure` attribute means browsers refuse to
  send the cookie over plaintext — a downgrade from HTTPS to HTTP can't
  steal the session.
- **Cloudflare WAF**: enable "Bot Fight Mode" and the basic managed
  rules in the Cloudflare dashboard if you haven't. Free tier covers it
  and catches the common scanner traffic.
- **Audit log**: not implemented in the app. If you need it, the
  uvicorn access log captures every request; configure
  `journalctl -u docker --output=json` to feed your aggregator.

## Day-2 ops on a public deploy

The `INSTALL.md` ops section still applies (logs, restart, upgrade).
Three additions specific to the internet exposure:

- **Watch login attempts**:
  ```sh
  docker compose logs app | grep 'POST /api/auth/login'
  ```
  Repeated 401s from the same source-IP suggest brute-force; consider
  adding fail2ban targeting the nginx error log.

- **Cloudflare access logs**: free tier doesn't include them, but the
  Cloudflare analytics dashboard shows traffic patterns. Worth glancing
  at weekly.

- **Cert renewal**: nothing to do — Cloudflare handles the public cert,
  and the connections behind the tunnel are plaintext-internal.
