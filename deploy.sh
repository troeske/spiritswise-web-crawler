#!/bin/bash
# ===========================================
# SpiritsWise Web Crawler Deployment Script
# ===========================================

set -e  # Exit on error

echo "=== Step 1: Clone repository ==="
cd /opt
if [ -d "spiritswise-web-crawler" ]; then
    echo "Directory exists, pulling latest..."
    cd spiritswise-web-crawler
    git pull origin master
else
    git clone https://github.com/troeske/spiritswise-web-crawler.git
    cd spiritswise-web-crawler
fi

echo "=== Step 2: Create virtual environment ==="
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "=== Step 3: Install Playwright browsers ==="
playwright install chromium
playwright install-deps chromium

echo "=== Step 4: Create .env.production ==="
# Get database password from AI Enhancement Service
DB_PASSWORD=$(grep DB_PASSWORD /opt/spiritswise-ai-enhancement-service/.env.production 2>/dev/null | cut -d'=' -f2 || echo "")

cat > .env.production << 'ENVEOF'
# Django Settings
SECRET_KEY=crawler-prod-$(openssl rand -hex 32)
DJANGO_ENV=production
DEBUG=False
ALLOWED_HOSTS=167.235.75.199,localhost,127.0.0.1

# Database (shared with AI Enhancement Service)
DB_NAME=spiritswise
DB_USER=spiritswise
DB_PASSWORD=PLACEHOLDER_DB_PASSWORD
DB_HOST=localhost
DB_PORT=5432

# Redis (use different DB number than AI service)
REDIS_URL=redis://localhost:6379/2
CELERY_BROKER_URL=redis://localhost:6379/2
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# AI Enhancement Service (local)
AI_ENHANCEMENT_SERVICE_URL=http://127.0.0.1:8000
AI_ENHANCEMENT_SERVICE_TOKEN=

# External API Keys
SERPAPI_API_KEY=86dc430939860e8775ca38fe37b279b93b191f560f83b5a9b0b0f37dab3e697d
SCRAPINGBEE_API_KEY=U9T8N36G3Z8LL2VLVY86S1LJJ83R33C79A4EYXYYRNSMQFCS2JPPQJX6OQ8RMPHXZS4LE2H8J25JJHZI

# Sentry Monitoring
SENTRY_DSN=https://1790c5e0bd71082316ed75211b466a1b@o4510611012911104.ingest.de.sentry.io/4510611100467280
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=1.0
SENTRY_PROFILE_SAMPLE_RATE=1.0

# Crawler Configuration
CRAWLER_REQUEST_TIMEOUT=30
CRAWLER_MAX_RETRIES=3
CRAWLER_RATE_LIMIT_DELAY=1.0
ENVEOF

# Replace DB password if found
if [ -n "$DB_PASSWORD" ]; then
    sed -i "s/PLACEHOLDER_DB_PASSWORD/$DB_PASSWORD/" .env.production
    echo "Database password copied from AI Enhancement Service"
else
    echo "WARNING: Could not find DB_PASSWORD. Please update .env.production manually."
fi

echo "=== Step 5: Run migrations ==="
export DJANGO_ENV=production
python manage.py migrate

echo "=== Step 6: Load fixtures ==="
python manage.py loaddata initial_sources initial_keywords competition_sources

echo "=== Step 7: Collect static files ==="
python manage.py collectstatic --noinput

echo "=== Step 8: Create systemd services ==="

# Celery Worker Service
cat > /etc/systemd/system/crawler-worker.service << 'EOF'
[Unit]
Description=SpiritsWise Crawler Celery Worker
After=network.target redis.service postgresql.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/spiritswise-web-crawler
Environment=DJANGO_ENV=production
ExecStart=/opt/spiritswise-web-crawler/venv/bin/celery -A config worker -l info -Q crawl,search --concurrency=4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Celery Beat Service
cat > /etc/systemd/system/crawler-beat.service << 'EOF'
[Unit]
Description=SpiritsWise Crawler Celery Beat
After=network.target redis.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/spiritswise-web-crawler
Environment=DJANGO_ENV=production
ExecStart=/opt/spiritswise-web-crawler/venv/bin/celery -A config beat -l info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Django Admin Server (optional, for admin access)
cat > /etc/systemd/system/crawler-admin.service << 'EOF'
[Unit]
Description=SpiritsWise Crawler Admin Server
After=network.target postgresql.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/spiritswise-web-crawler
Environment=DJANGO_ENV=production
ExecStart=/opt/spiritswise-web-crawler/venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8001 --workers 2
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo "=== Step 9: Enable and start services ==="
systemctl daemon-reload
systemctl enable crawler-worker crawler-beat crawler-admin
systemctl start crawler-worker crawler-beat crawler-admin

echo "=== Step 10: Check service status ==="
systemctl status crawler-worker --no-pager
systemctl status crawler-beat --no-pager
systemctl status crawler-admin --no-pager

echo ""
echo "=========================================="
echo "Deployment complete!"
echo "=========================================="
echo ""
echo "Services running:"
echo "  - Celery Worker: systemctl status crawler-worker"
echo "  - Celery Beat:   systemctl status crawler-beat"
echo "  - Admin Server:  http://127.0.0.1:8001/admin/"
echo ""
echo "Next steps:"
echo "  1. Create admin user: cd /opt/spiritswise-web-crawler && source venv/bin/activate && python manage.py createsuperuser"
echo "  2. Configure nginx to proxy port 8001 (optional)"
echo ""
echo "View logs:"
echo "  - Worker: journalctl -u crawler-worker -f"
echo "  - Beat:   journalctl -u crawler-beat -f"
echo ""
