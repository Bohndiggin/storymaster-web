# Storymaster deploy runbook

Single-host deploy: nginx in front, uvicorn behind, Postgres for state.
Backups run nightly via systemd timer.

## Layout

```
/opt/storymaster/             # checked-out repo
/opt/storymaster/.venv/       # python venv with requirements.txt installed
/opt/storymaster/web/dist/    # built SPA bundle (npm run build)
/etc/storymaster/storymaster.env   # secrets (DB password, etc.)
/var/backups/storymaster/     # pg_dump archives
/var/log/storymaster/         # optional log target
```

A dedicated `storymaster` system user owns `/opt/storymaster` and
`/var/backups/storymaster`. nginx runs as its own user; only `/opt/storymaster/web/dist`
needs to be world-readable.

## First install

1. **Provision Postgres.**
   ```sh
   sudo -u postgres createuser --pwprompt storymaster
   sudo -u postgres createdb -O storymaster storymaster
   ```

2. **Create the system user + dirs.**
   ```sh
   sudo useradd --system --create-home --home /opt/storymaster --shell /bin/bash storymaster
   sudo install -d -o storymaster -g storymaster /var/log/storymaster /var/backups/storymaster
   sudo install -d -o root      -g storymaster -m 0750 /etc/storymaster
   ```

3. **Check out the repo + install Python deps.**
   ```sh
   sudo -u storymaster git clone https://github.com/Bohndiggin/storymaster /opt/storymaster
   sudo -u storymaster python3 -m venv /opt/storymaster/.venv
   sudo -u storymaster /opt/storymaster/.venv/bin/pip install -r /opt/storymaster/requirements.txt
   ```

4. **Build the SPA.**
   ```sh
   cd /opt/storymaster/web && sudo -u storymaster npm ci && sudo -u storymaster npm run build
   ```

5. **Drop in env + secrets.**
   ```sh
   sudo cp /opt/storymaster/deploy/storymaster.env.example /etc/storymaster/storymaster.env
   sudo chmod 0640 /etc/storymaster/storymaster.env
   sudo chown root:storymaster /etc/storymaster/storymaster.env
   sudoedit /etc/storymaster/storymaster.env   # set STORYMASTER_DB_URL, SYNC_SECRET_KEY
   ```

6. **Run migrations.**
   ```sh
   cd /opt/storymaster
   sudo -u storymaster bash -c '
     set -a; source /etc/storymaster/storymaster.env; set +a
     PYTHONPATH=. .venv/bin/alembic upgrade head'
   ```

7. **Create the first admin user.**
   ```sh
   sudo -u storymaster bash -c '
     set -a; source /etc/storymaster/storymaster.env; set +a
     PYTHONPATH=. .venv/bin/python -m storymaster.api.scripts.create_admin --username admin'
   ```

8. **Install + enable systemd units.**
   ```sh
   sudo cp /opt/storymaster/deploy/storymaster-api.service     /etc/systemd/system/
   sudo cp /opt/storymaster/deploy/storymaster-backup.service  /etc/systemd/system/
   sudo cp /opt/storymaster/deploy/storymaster-backup.timer    /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now storymaster-api.service storymaster-backup.timer
   ```

9. **Wire up nginx.**
   ```sh
   sudo cp /opt/storymaster/deploy/nginx.conf /etc/nginx/sites-available/storymaster
   sudo sed -i 's/storymaster.example.com/<your hostname>/g' /etc/nginx/sites-available/storymaster
   sudo ln -s ../sites-available/storymaster /etc/nginx/sites-enabled/storymaster
   sudo certbot --nginx -d <your hostname>
   sudo systemctl reload nginx
   ```

10. **Smoke test.**
    ```sh
    curl -fsS https://<host>/api/health
    # → {"status":"ok",...}
    ```

## Upgrade

```sh
cd /opt/storymaster
sudo systemctl stop storymaster-api.service

sudo -u storymaster git pull --ff-only
sudo -u storymaster .venv/bin/pip install -r requirements.txt
sudo -u storymaster bash -c 'cd web && npm ci && npm run build'

sudo -u storymaster bash -c '
  set -a; source /etc/storymaster/storymaster.env; set +a
  PYTHONPATH=. .venv/bin/alembic upgrade head'

sudo systemctl start storymaster-api.service
curl -fsS https://<host>/api/health
```

If the migration fails, the old code is still installed and the previous
SPA bundle is in place — just don't run `git pull`/`npm run build` for
the failed migration; restart the service to bring the previous code
back up. Recovery from a bad migration is via the backup (see below).

## Backups

Nightly automatic via `storymaster-backup.timer`. Manual:

```sh
sudo systemctl start storymaster-backup.service
sudo journalctl -u storymaster-backup.service --since today
```

Restore from a backup:

```sh
# 1. Stop the API so no concurrent writes hit the database during restore.
sudo systemctl stop storymaster-api.service

# 2. Recreate an empty database (drop + create) — pg_restore --clean works
#    against a populated DB but a fresh one avoids dropped-object warnings.
sudo -u postgres psql -c "DROP DATABASE storymaster"
sudo -u postgres psql -c "CREATE DATABASE storymaster OWNER storymaster"

# 3. Restore the dump.
sudo -u storymaster pg_restore --no-owner -d "<DB_URL>" /var/backups/storymaster/<archive>.dump

# 4. Re-run alembic upgrade head against the restored DB. If the dump is
#    older than the current schema, this brings it forward.
sudo -u storymaster bash -c '
  cd /opt/storymaster
  set -a; source /etc/storymaster/storymaster.env; set +a
  PYTHONPATH=. .venv/bin/alembic upgrade head'

sudo systemctl start storymaster-api.service
```

## Operational notes

- `storymaster-api.service` is set to `Restart=on-failure`. uvicorn that
  crashes on startup will loop; check `journalctl -u storymaster-api -e`.
- `RestartSec=2s` is short on purpose — fast recovery from a transient
  database hiccup. Backoff isn't needed at the small-team scale.
- The `Sandbox` directives in the unit (`ProtectSystem=strict` etc.)
  prevent the API from writing anywhere except `/var/log/storymaster`
  and `/var/backups/storymaster`. If you add a feature that writes to
  disk somewhere new (e.g. a Storyweaver ZIP import staging dir), add it
  to `ReadWritePaths` first or the open() will EROFS.
- `client_max_body_size 10m` in nginx caps individual API request bodies.
  Raise this for `.storyweaver` ZIP imports (Phase 6 deferred work).
