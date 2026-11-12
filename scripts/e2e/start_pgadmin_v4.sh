#!/bin/sh
# Standalone pgAdmin for the rain4 stack (not in compose, like rain3-pgadmin): http://localhost:5052
# Login admin@rain.app / admin. Servers and passwords are written by the entrypoint; settings persist in rain4_pgadmindata.
SERVERS='{"Servers":{"1":{"Name":"RAIN v4 - postgres (admin)","Group":"RAIN v4","Host":"postgres","Port":5432,"MaintenanceDB":"rain_v4","Username":"postgres","PassFile":"/pgpass","SSLMode":"prefer","Comment":"rain4 stack Postgres (host port 55436). Databases: rain_v4 (PRD v0.4 wave), rain (v0.2 seed)."},"2":{"Name":"RAIN v4 - rain_app (backend login)","Group":"RAIN v4","Host":"postgres","Port":5432,"MaintenanceDB":"rain_v4","Username":"rain_app","PassFile":"/pgpass","SSLMode":"prefer","Comment":"The read-only login the backend /api/v4 routers use."}}}'
docker rm -f rain4-pgadmin >/dev/null 2>&1
docker run -d --name rain4-pgadmin --restart unless-stopped --network rain4_default -p 5052:80 \
  -v rain4_pgadmindata:/var/lib/pgadmin \
  -e PGADMIN_DEFAULT_EMAIL=admin@rain.app -e PGADMIN_DEFAULT_PASSWORD=admin \
  -e PGADMIN_CONFIG_CHECK_EMAIL_DELIVERABILITY=False -e PGADMIN_SERVER_JSON_FILE=/tmp/servers.json \
  -e "SERVERS_JSON=$SERVERS" --entrypoint /bin/sh dpage/pgadmin4:9.8 -c '
d="/var/lib/pgadmin/storage/$(echo "$PGADMIN_DEFAULT_EMAIL" | sed "s/@/_/")"
mkdir -p "$d"
printf "postgres:5432:*:postgres:root\npostgres:5432:*:rain_app:rain_dev_pw\n" > "$d/pgpass"
chmod 600 "$d/pgpass"
printf "%s" "$SERVERS_JSON" > /tmp/servers.json
exec /entrypoint.sh'
