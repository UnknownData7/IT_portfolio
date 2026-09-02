set -e

APP_DIR="$HOME/spb-heights"
DOMAIN="tutbudetdomen.ru"
EMAIL="bkmz7692@tutbudetdomen.ru"

read -p "Путь к архиву с геоджсонами: " DATA_ARCHIVE

apt-get update && apt-get install -y docker.io nginx certbot python3-certbot-nginx unzip git-lfs

if [ ! -f "$APP_DIR/.env" ]; then
    echo ".env не найден в $APP_DIR"
    exit 1
fi

MAPTILER_KEY=$(grep VITE_MAPTILER_KEY $APP_DIR/.env | cut -d '=' -f2)

mkdir -p $APP_DIR/public
unzip -o $DATA_ARCHIVE -d $APP_DIR/public/

cd $APP_DIR

docker build --build-arg VITE_MAPTILER_KEY=$MAPTILER_KEY -t spb-heights .

docker stop spb-heights 2>/dev/null || true
docker rm spb-heights 2>/dev/null || true

docker run -d \
    --name spb-heights \
    --restart always \
    -p 8080:80 \
    -v $APP_DIR/public/output.geojson:/usr/share/nginx/html/output.geojson:ro \
    -v $APP_DIR/public/zones.geojson:/usr/share/nginx/html/zones.geojson:ro \
    spb-heights

cat > /etc/nginx/sites-available/spb-heights << NGINX
server {
    listen 80;
    server_name $DOMAIN;

    gzip on;
    gzip_types application/json text/plain application/javascript text/css;
    gzip_comp_level 9;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
    }
}
NGINX

ln -sf /etc/nginx/sites-available/spb-heights /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m $EMAIL

echo "done: https://$DOMAIN"