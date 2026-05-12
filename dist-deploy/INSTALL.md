# Storymaster — Rocky Linux deploy

Pre-built deploy bundle. Three files:

- `storymaster-web.tar.gz` — the Docker image (~336 MB compressed, ~1.4 GB on disk).
- `docker-compose.yml` — references `storymaster-web:latest`; no source tree needed.
- `.env.example` — runtime config template.

## On your dev box

You're reading this after running on the dev box:

```sh
docker save storymaster-web:latest | gzip -1 > storymaster-web.tar.gz
```

Ship the bundle to the server:

```sh
scp -r dist-deploy/ user@server:/opt/storymaster/
```

## On the Rocky server

### 1. Install Docker (one-time)

```sh
sudo dnf -y install dnf-plugins-core
sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo dnf -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
# Log out and back in for the group change to take effect.
docker run --rm hello-world          # smoke check
```

### 2. Load the image

```sh
cd /opt/storymaster
docker load < storymaster-web.tar.gz
docker images storymaster-web        # should show :latest, ~1.4 GB
```

### 3. Configure runtime env

```sh
cp .env.example .env
vim .env                             # set STORYMASTER_DB_URL + SYNC_SECRET_KEY
chmod 600 .env
```

The DB URL points at your existing Postgres. Format:

    postgresql+psycopg://USERNAME:PASSWORD@HOST:5432/DATABASE

If Postgres is on the same host: `localhost` works **only** if the
container's network can reach it. The simplest reliable option is to
bind Postgres to the Rocky host's LAN address (e.g. `192.168.68.116`)
and use that here too. Or install Postgres into compose alongside (see
the commented `postgres:` block in the original repo's
`docker-compose.yml`).

### 4. Generate `SYNC_SECRET_KEY`

```sh
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
# paste the output into .env as SYNC_SECRET_KEY=...
```

### 5. SELinux: prep the backup directory

Rocky enforces SELinux by default. The compose file uses `:Z` on the
backup bind mount so Docker relabels it for the container, but you
need to create the directory first:

```sh
mkdir -p /opt/storymaster/backups
```

If you've disabled SELinux (`getenforce` says `Disabled`), edit
`docker-compose.yml` and remove the `:Z` suffix from the volume mount.

### 6. Open the firewall (if not behind a reverse proxy)

If the container's port should be reachable from the LAN directly,
edit `docker-compose.yml` and change

    - "127.0.0.1:8765:8765"

to

    - "8765:8765"

then:

```sh
sudo firewall-cmd --add-port=8765/tcp --permanent
sudo firewall-cmd --reload
```

For an HTTPS deploy via host nginx, leave the port on `127.0.0.1` and
proxy from nginx instead. The `deploy/nginx.conf` in the source repo
is a working starting point.

### 7. Start the app

```sh
docker compose up -d
docker compose logs -f app
```

The first start runs `alembic upgrade head` against your Postgres,
then boots uvicorn. Watch the log output — startup is ~5 seconds.

### 8. Create the first admin user

```sh
docker compose exec app \
    python -m storymaster.api.scripts.create_admin --username alice
# you'll be prompted for the password
```

### 9. Smoke test

```sh
curl -fsS http://127.0.0.1:8765/api/health
# → {"status":"ok",...,"database_connected":true,...}

docker compose ps
# STATUS column should say (healthy) after ~30 seconds
```

Open http://server-ip:8765 (or wherever you proxy it) and log in as
the admin user.

## Day-2 ops

### Logs

```sh
docker compose logs -f app           # follow
docker compose logs --since 1h app   # last hour
```

### Restart after config change

```sh
docker compose down
docker compose up -d
```

`docker compose restart app` doesn't re-read `.env` reliably; `down + up`
does.

### Upgrade

When you build a new image on your dev box, repeat steps 1-2:

```sh
# dev box
docker save storymaster-web:latest | gzip -1 > storymaster-web.tar.gz
scp storymaster-web.tar.gz user@server:/opt/storymaster/

# server
cd /opt/storymaster
docker compose down
docker load < storymaster-web.tar.gz
docker compose up -d
```

The entrypoint runs `alembic upgrade head` on every start, so schema
changes apply automatically. Watch the logs on first boot of a new
image to confirm migrations succeeded.

### Backups

The image ships with `scripts/backup_postgres.sh`. To run it from inside
the container:

```sh
docker compose exec -e BACKUP_DIR=/var/backups/storymaster \
    app /bin/bash /app/scripts/backup_postgres.sh
```

Output lands in `/opt/storymaster/backups/` on the host (the bind mount).

For automation, add a host cron entry that calls the same exec.

### Stop

```sh
docker compose down                  # stops and removes the container
docker compose stop                  # stops but keeps the container
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `STORYMASTER_DB_URL is not set` on start | `.env` missing or unreadable | `ls -la .env` — must be in the same dir as `docker-compose.yml`; `chmod 600` is fine, but make sure the file's there |
| `connection refused` to Postgres | Postgres bound to `localhost` only on host | Bind PG to LAN address, then put that address in `.env` |
| Container restart-loops | Migration error | `docker compose logs app` — usually a permissions issue on the DB user |
| `permission denied` on `/var/backups/storymaster` | SELinux relabel didn't run | Recreate the directory: `rm -rf backups && mkdir backups` then `docker compose down && up -d`; the `:Z` suffix relabels on container start |
| `port already in use` | Another service on 8765 | `ss -lntp | grep 8765` — change the host-side port in `docker-compose.yml` (e.g. `127.0.0.1:8770:8765`) |
| `unhealthy` status forever | Migration stuck or Postgres unreachable | `docker compose logs app` — startup logs include the alembic phase |
