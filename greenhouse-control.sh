#!/bin/bash
# Greenhouse Control System Service Management Script

case "$1" in
    start)
        echo "Starting Greenhouse Control Services..."
        sudo systemctl start greenhouse-scheduler.service
        sudo systemctl start greenhouse-web.service
        echo "Services started. Check status with: $0 status"
        ;;
    stop)
        echo "Stopping Greenhouse Control Services..."
        sudo systemctl stop greenhouse-web.service
        sudo systemctl stop greenhouse-scheduler.service
        echo "Services stopped."
        ;;
    restart)
        echo "Restarting Greenhouse Control Services..."
        sudo systemctl restart greenhouse-scheduler.service
        sudo systemctl restart greenhouse-web.service
        echo "Services restarted."
        ;;
    status)
        echo "=== Greenhouse Scheduler Service ==="
        sudo systemctl status greenhouse-scheduler.service --no-pager -l
        echo
        echo "=== Greenhouse Web Service ==="
        sudo systemctl status greenhouse-web.service --no-pager -l
        echo
        echo "=== Web Server Test ==="
        if curl -s http://127.0.0.1:5000/api/status > /dev/null; then
            echo "✅ Web server responding at http://127.0.0.1:5000"
        else
            echo "❌ Web server not responding"
        fi
        ;;
    logs)
        if [ "$2" = "web" ]; then
            sudo journalctl -u greenhouse-web.service -f
        elif [ "$2" = "scheduler" ]; then
            sudo journalctl -u greenhouse-scheduler.service -f
        else
            echo "Following logs for both services (Ctrl+C to exit):"
            sudo journalctl -u greenhouse-scheduler.service -u greenhouse-web.service -f
        fi
        ;;
    logs-web)
        sudo journalctl -u greenhouse-web.service -f
        ;;
    logs-scheduler)
        sudo journalctl -u greenhouse-scheduler.service -f
        ;;
    install)
        echo "Installing Greenhouse Control Services..."
        sudo cp greenhouse-scheduler.service /etc/systemd/system/
        sudo cp greenhouse-web.service /etc/systemd/system/
        sudo cp start-scheduler.sh /usr/local/bin/
        sudo cp start-web-server.sh /usr/local/bin/
        sudo chmod +x /usr/local/bin/start-scheduler.sh
        sudo chmod +x /usr/local/bin/start-web-server.sh
        sudo systemctl daemon-reload
        echo "Services installed. Enable with: $0 enable"
        ;;
    uninstall)
        echo "Uninstalling Greenhouse Control Services..."
        sudo systemctl stop greenhouse-scheduler.service greenhouse-web.service 2>/dev/null || true
        sudo systemctl disable greenhouse-scheduler.service greenhouse-web.service 2>/dev/null || true
        sudo rm -f /etc/systemd/system/greenhouse-scheduler.service
        sudo rm -f /etc/systemd/system/greenhouse-web.service
        sudo rm -f /usr/local/bin/start-scheduler.sh
        sudo rm -f /usr/local/bin/start-web-server.sh
        sudo systemctl daemon-reload
        echo "Services uninstalled."
        ;;
    enable)
        echo "Enabling services to start on boot..."
        sudo systemctl enable greenhouse-scheduler.service
        sudo systemctl enable greenhouse-web.service
        echo "Services enabled."
        ;;
    disable)
        echo "Disabling services from starting on boot..."
        sudo systemctl disable greenhouse-scheduler.service
        sudo systemctl disable greenhouse-web.service
        echo "Services disabled."
        ;;
    *)
        echo "Greenhouse Control System Service Manager"
        echo "Usage: $0 {start|stop|restart|status|logs|enable|disable|install|uninstall}"
        echo
        echo "Service Management:"
        echo "  start         - Start both scheduler and web services"
        echo "  stop          - Stop both services"
        echo "  restart       - Restart both services"
        echo "  status        - Show status of both services"
        echo "  enable        - Enable services to start on boot"
        echo "  disable       - Disable services from starting on boot"
        echo
        echo "Logging:"
        echo "  logs          - Show logs for both services"
        echo "  logs web      - Show web service logs only"
        echo "  logs scheduler - Show scheduler service logs only"
        echo "  logs-web      - Show web service logs only (shortcut)"
        echo "  logs-scheduler - Show scheduler service logs only (shortcut)"
        echo
        echo "Installation:"
        echo "  install       - Install systemd service files"
        echo "  uninstall     - Remove systemd service files"
        echo
        echo "Web Interface: http://127.0.0.1:5000"
        exit 1
        ;;
esac