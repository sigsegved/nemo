# Deployment Documentation

## Nemo Volatility Harvest Bot Deployment Guide

### Prerequisites

- Python 3.9 or higher
- Required dependencies (see `requirements.txt`)
- Configuration file (`config.yaml`)

### Installation

1. **Clone the repository and install dependencies:**
   ```bash
   git clone <repository-url>
   cd nemo
   pip install -r requirements.txt
   pip install -e .
   ```

2. **Configure the bot:**
   ```bash
   # Copy and modify the configuration file
   cp config.yaml.example config.yaml
   # Edit config.yaml with your settings
   ```

### Configuration

The `config.yaml` file should contain:

```yaml
# Trading Configuration
base_equity: 100000              # Base capital in USD
cooldown_hours: 6                # Cooldown after stop losses
symbols: ["BTCUSD", "ETHUSD"]    # Trading symbols
paper_trading: true              # Use paper trading mode
max_positions: 5                 # Maximum concurrent positions

# System Configuration
log_level: "INFO"                # Logging level (DEBUG, INFO, WARN, ERROR)
log_format: "console"            # Log format (console, json)
metrics_port: 8000               # Prometheus metrics port

# Risk Management
max_equity_per_position: 0.25    # 25% max per position
max_leverage: 3.0                # Maximum leverage
slippage_threshold_bps: 15       # Slippage threshold (basis points)
```

### Running the Bot

#### Paper Trading Mode (Recommended)
```bash
python -m src.main --paper-trading --config config.yaml
```

#### Live Trading Mode (Use with Caution)
```bash
python -m src.main --live-trading --config config.yaml
```

### Monitoring

#### Prometheus Metrics

The bot exposes Prometheus metrics on port 8000 (configurable):

- `nemo_trade_signals_total` - Total trade signals generated
- `nemo_positions_active` - Number of active positions
- `nemo_circuit_breaker_active` - Circuit breaker status
- `nemo_signal_processing_seconds` - Signal processing time
- `nemo_health_check_status` - Health check status

Access metrics at: `http://localhost:8000/metrics`

#### Log Monitoring

Logs are output to stdout in structured format. Use log aggregation tools like:
- ELK Stack (Elasticsearch, Logstash, Kibana)
- Prometheus + Grafana
- Splunk
- Datadog

#### Health Checks

Health status available via the orchestrator status endpoint or metrics.

### Deployment Options

#### 1. Direct Deployment

```bash
# Create systemd service (Linux)
sudo tee /etc/systemd/system/nemo-bot.service > /dev/null <<EOF
[Unit]
Description=Nemo Volatility Harvest Bot
After=network.target

[Service]
Type=exec
User=nemo
WorkingDirectory=/opt/nemo
ExecStart=/opt/nemo/venv/bin/python -m src.main --paper-trading --config config.yaml
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
sudo systemctl enable nemo-bot
sudo systemctl start nemo-bot
```

#### 2. Docker Deployment (Optional)

Create `Dockerfile`:
```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY config.yaml ./
COPY setup.py ./

# Install package
RUN pip install -e .

# Create non-root user
RUN useradd --create-home --shell /bin/bash nemo
USER nemo

# Expose metrics port
EXPOSE 8000

# Run the application
CMD ["python", "-m", "src.main", "--paper-trading", "--config", "config.yaml"]
```

Build and run:
```bash
docker build -t nemo-bot .
docker run -d --name nemo-bot -p 8000:8000 nemo-bot
```

#### 3. Docker Compose (Recommended for Production)

Create `docker-compose.yml`:
```yaml
version: '3.8'

services:
  nemo-bot:
    build: .
    container_name: nemo-bot
    restart: unless-stopped
    ports:
      - "8000:8000"  # Metrics port
    environment:
      - PYTHONUNBUFFERED=1
    volumes:
      - ./config.yaml:/app/config.yaml:ro
      - ./logs:/app/logs
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/metrics"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  prometheus:
    image: prom/prometheus:latest
    container_name: nemo-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'

  grafana:
    image: grafana/grafana:latest
    container_name: nemo-grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-storage:/var/lib/grafana

volumes:
  grafana-storage:
```

### Security Considerations

1. **API Keys**: Never commit API keys or secrets to version control
2. **Network Security**: Use firewalls to restrict access to metrics endpoints
3. **User Permissions**: Run the bot with minimal required permissions
4. **Monitoring**: Set up alerts for unusual trading activity
5. **Backups**: Regularly backup configuration and logs

### Troubleshooting

#### Common Issues

1. **Import Errors**: Ensure package is installed with `pip install -e .`
2. **Configuration Errors**: Validate YAML syntax in config file
3. **Permission Errors**: Check file permissions and user access
4. **Port Conflicts**: Ensure metrics port is available
5. **Memory Issues**: Monitor memory usage, especially with large datasets

#### Debug Mode

Enable debug logging:
```yaml
log_level: "DEBUG"
```

#### Health Check Commands

```bash
# Check if bot is running
systemctl status nemo-bot

# View recent logs
journalctl -u nemo-bot -f

# Check metrics
curl http://localhost:8000/metrics

# Check process
ps aux | grep python | grep main
```

### Performance Tuning

1. **Memory**: Adjust `max_data_points` in VWAP calculators for memory usage
2. **CPU**: Use uvloop for better async performance (Linux/macOS)
3. **Network**: Optimize API call frequency and batch requests
4. **Storage**: Use SSD for logs and temporary files

### Backup and Recovery

1. **Configuration**: Keep versioned backups of `config.yaml`
2. **Logs**: Set up log rotation and archival
3. **State**: The bot is stateless by design for easier recovery
4. **Monitoring**: Set up external monitoring for critical metrics

### Support

- Check logs first for error messages
- Verify configuration file syntax
- Ensure all dependencies are installed
- Test with paper trading before live deployment
- Monitor resource usage and performance metrics