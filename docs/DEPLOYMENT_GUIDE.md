# Greenhouse Control System - Production Deployment Guide

## Overview

This guide covers deploying the Greenhouse Control System as a production service with systemd integration, performance optimization, and monitoring capabilities.

## Architecture

### Service Stack

**🌐 Web Service (`greenhouse-web.service`)**
- Primary Flask application serving dashboard and REST API
- Uses cached sensor data for optimal performance (~400ms response times)
- Handles user interactions, configuration, and intelligent lighting control
- Auto-restart on failure with graceful signal handling

**📊 Sensor Scheduler Service (`sensor_scheduler_service.py`)**  
- Background sensor data collection service
- Continuous monitoring with 6-band spectral analysis
- Writes to `sensor_readings.json` for web service consumption
- Adaptive sensor management with gain/integration optimization
- Ready for systemd service conversion

**🛠️ Management Tools**
- `greenhouse-control.sh`: Unified service management
- `start-web-server.sh`: Environment wrapper for web service
- Built-in logging, monitoring, and restart capabilities

## Quick Deployment

### Automated Installation

```bash
# Clone repository
git clone https://github.com/shawnj82/greenhouse-control-system.git
cd greenhouse-control-system

# Setup Python environment  
python3 -m venv greenhouse-env
source greenhouse-env/bin/activate
pip install -r requirements.txt

# Install as systemd service
sudo ./greenhouse-control.sh install

# Start services
sudo systemctl start greenhouse-web.service
sudo systemctl enable greenhouse-web.service

# Verify deployment
./greenhouse-control.sh status
curl http://localhost:5000/api/status
```

### Manual Installation

```bash
# Copy service files
sudo cp greenhouse-web.service /etc/systemd/system/
sudo cp start-web-server.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/start-web-server.sh

# Install and start service
sudo systemctl daemon-reload  
sudo systemctl enable greenhouse-web.service
sudo systemctl start greenhouse-web.service
```

## Service Management

### Using greenhouse-control.sh

```bash
# Service control
./greenhouse-control.sh start     # Start all services
./greenhouse-control.sh stop      # Stop all services  
./greenhouse-control.sh restart   # Restart all services
./greenhouse-control.sh status    # Check service status

# Monitoring
./greenhouse-control.sh logs      # View live logs (all services)
./greenhouse-control.sh logs-web  # Web server logs only

# Installation
sudo ./greenhouse-control.sh install    # Install systemd services
sudo ./greenhouse-control.sh uninstall  # Remove systemd services
```

### Direct systemctl Commands

```bash
# Service operations
sudo systemctl start greenhouse-web.service
sudo systemctl stop greenhouse-web.service  
sudo systemctl restart greenhouse-web.service
sudo systemctl status greenhouse-web.service

# Enable/disable auto-start
sudo systemctl enable greenhouse-web.service
sudo systemctl disable greenhouse-web.service

# View logs
sudo journalctl -u greenhouse-web.service -f
sudo journalctl -u greenhouse-web.service --since "1 hour ago"
```

## Performance Optimization

### Dashboard Performance

The system has been optimized for production performance:

**Before Optimization:**
- Dashboard load time: 3+ seconds  
- Blocking sensor reads during web requests
- UI freezing during auto-refresh

**After Optimization:**
- Dashboard load time: ~400ms (8x improvement)
- Non-blocking cached sensor data access
- Smart auto-refresh preserving form state

### Sensor Data Architecture

**Background Scheduler Service:**
```bash
# Start sensor scheduler (for cached data)
python sensor_scheduler_service.py &

# Web service uses cached readings from:
cat sensor_readings.json
```

**Benefits:**
- Instant dashboard response using cached data
- Continuous sensor monitoring independent of web traffic  
- Adaptive sensor management with quality indicators
- 6-band spectral analysis (UV-A, Blue, Green, Red, Far-Red, NIR)

## Monitoring and Maintenance

### Health Checks

```bash
# System health
./greenhouse-control.sh status

# API health check
curl -f http://localhost:5000/api/status || echo "API Down"

# Service auto-restart status
systemctl is-enabled greenhouse-web.service

# Resource usage
systemctl status greenhouse-web.service | grep -E "(Active|Memory|CPU)"
```

### Log Management

```bash
# Live monitoring
./greenhouse-control.sh logs | grep -E "(ERROR|WARNING|INFO)"

# Log analysis
sudo journalctl -u greenhouse-web.service --since today | grep ERROR
sudo journalctl -u greenhouse-web.service --since "1 hour ago" --until "30 minutes ago"

# Log rotation (automatic via systemd)
# Logs are automatically rotated by systemd journal
sudo journalctl --disk-usage
sudo journalctl --vacuum-time=30d  # Keep 30 days of logs
```

### Backup and Recovery

```bash
# Backup configuration
cp -r data/ backup/data-$(date +%Y%m%d)/

# Backup service configuration  
sudo cp /etc/systemd/system/greenhouse-web.service backup/
cp greenhouse-control.sh start-web-server.sh backup/

# Service recovery
sudo systemctl daemon-reload
sudo systemctl restart greenhouse-web.service
./greenhouse-control.sh status
```

## Security Considerations

### Network Security

```bash
# Bind to localhost only (default)
# Edit start-web-server.sh to change host binding

# For remote access, use reverse proxy (nginx/apache)
sudo apt install nginx
# Configure proxy to localhost:5000
```

### File Permissions

```bash
# Ensure proper ownership
sudo chown -R $USER:$USER /home/$USER/greenhouse-control-system
chmod +x greenhouse-control.sh start-web-server.sh

# Protect configuration files
chmod 644 data/*.json
chmod 755 data/
```

### Service Isolation

```bash
# Service runs as current user (not root)
grep User /etc/systemd/system/greenhouse-web.service

# Virtual environment isolation
ls -la greenhouse-env/

# Network binding (localhost only by default)
netstat -tlnp | grep 5000
```

## Nginx Reverse Proxy Setup

For production external access:

```bash
# Install nginx
sudo apt install nginx

# Create site configuration
sudo nano /etc/nginx/sites-available/greenhouse
```

Nginx configuration:
```nginx
server {
    listen 80;
    server_name greenhouse.local;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
}
```

Enable and start:
```bash
sudo ln -s /etc/nginx/sites-available/greenhouse /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## Troubleshooting

### Common Issues

**Service Won't Start:**
```bash
# Check service status and logs
./greenhouse-control.sh status
./greenhouse-control.sh logs-web

# Test components individually  
./start-web-server.sh  # Test wrapper script
source greenhouse-env/bin/activate && python web_app.py  # Test Flask app
```

**Performance Issues:**
```bash
# Check sensor scheduler
ps aux | grep sensor_scheduler
ls -la sensor_readings.json

# Monitor response times
time curl http://localhost:5000/api/status
./greenhouse-control.sh logs-web | grep "GET /"
```

**Configuration Problems:**
```bash
# Validate JSON files
python -m json.tool data/zones.json
python -m json.tool data/lights.json  

# Check file permissions
ls -la data/
ls -la *.service *.sh
```

### Recovery Procedures

**Complete Service Reset:**
```bash
# Stop all services
./greenhouse-control.sh stop

# Reset configuration (backup first!)
cp -r data/ backup/data-$(date +%Y%m%d)/
git checkout HEAD -- data/

# Restart services
./greenhouse-control.sh start
./greenhouse-control.sh status
```

**Service Reinstallation:**
```bash
# Uninstall existing services
sudo ./greenhouse-control.sh uninstall

# Clean reinstall
sudo ./greenhouse-control.sh install
sudo systemctl start greenhouse-web.service
```

## Production Checklist

### Pre-Deployment

- [ ] Python environment configured with correct dependencies
- [ ] All configuration files validated and customized
- [ ] Hardware connections tested (sensors, relays, GPIO)
- [ ] Network connectivity verified
- [ ] Backup procedures established

### Post-Deployment  

- [ ] Services running and enabled for auto-start
- [ ] Web interface accessible and responsive  
- [ ] API endpoints returning valid data
- [ ] Sensor readings updating correctly
- [ ] Log rotation and monitoring configured
- [ ] Performance benchmarks established

### Monitoring Setup

- [ ] Health check scripts configured
- [ ] Log analysis tools setup  
- [ ] Alert mechanisms for service failures
- [ ] Performance monitoring dashboard
- [ ] Backup verification procedures

## Advanced Configuration

### Multiple Service Deployment

Convert sensor scheduler to systemd service:

```bash
# Create additional service file
sudo nano /etc/systemd/system/greenhouse-scheduler.service
```

Service configuration:
```ini
[Unit]
Description=Greenhouse Sensor Scheduler
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/home/$USER/greenhouse-control-system
Environment=PATH=/home/$USER/greenhouse-control-system/greenhouse-env/bin
ExecStart=/home/$USER/greenhouse-control-system/greenhouse-env/bin/python sensor_scheduler_service.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Load Balancing (Multiple Nodes)

For larger deployments:

```bash
# Deploy multiple web service instances
systemctl start greenhouse-web@{1..3}.service

# Configure nginx upstream
upstream greenhouse_backend {
    server 127.0.0.1:5000;
    server 127.0.0.1:5001;  
    server 127.0.0.1:5002;
}
```

### High Availability

```bash
# Configure service dependencies
sudo systemctl edit greenhouse-web.service

# Add override:
[Unit]
Wants=greenhouse-scheduler.service
After=greenhouse-scheduler.service

[Service]
Restart=always
RestartSec=5
```

## Support and Maintenance

### Regular Maintenance Tasks

**Daily:**
- Check service status via monitoring dashboard
- Review error logs for anomalies
- Verify sensor data accuracy

**Weekly:**  
- Backup configuration files
- Update system packages (sudo apt update && sudo apt upgrade)
- Review performance metrics

**Monthly:**
- Clean old log files (sudo journalctl --vacuum-time=30d)  
- Update Python dependencies (pip list --outdated)
- Test backup/recovery procedures

### Performance Benchmarks

**Target Metrics:**
- Dashboard load time: < 500ms
- API response time: < 200ms  
- Service restart time: < 10s
- Memory usage: < 100MB per service
- CPU usage: < 5% average

**Monitoring Commands:**
```bash
# Response time testing
time curl -s http://localhost:5000/ > /dev/null

# Resource usage monitoring  
systemctl status greenhouse-web.service | grep -E "(Memory|CPU)"

# Service performance
./greenhouse-control.sh logs-web | grep -E "GET|POST" | tail -20
```

---

For additional support, refer to the main README.md and documentation in the `docs/` directory.