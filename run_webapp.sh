#!/bin/bash
# Runner script for Route4Me - Shopify Dashboard Web UI

# Make scripts executable if they aren't already
chmod +x app.py
chmod +x route4me_shopify_dashboard.py

# Check if .env file exists, create from example if it doesn't
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "Creating .env file from .env.example..."
        cp .env.example .env
        echo "Please review and update the values in .env before running again."
        exit 1
    else
        echo "Error: No .env or .env.example file found."
        exit 1
    fi
fi

# Check if the Python virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    echo "Installing dependencies..."
    pip install -r requirements.txt
    
    # Update certificates
    echo "Updating SSL certificates..."
    pip install --upgrade certifi
else
    source venv/bin/activate
    # Check if we need to update dependencies
    if [ requirements.txt -nt venv/pip-selfcheck.json ]; then
        echo "Updating dependencies..."
        pip install -r requirements.txt
    fi
    
    # Always ensure certificates are up-to-date
    echo "Updating SSL certificates..."
    pip install --upgrade certifi
fi

# Print certificate path for debugging
CERT_PATH=$(python -c "import certifi; print(certifi.where())")
echo "Using certificates from: ${CERT_PATH}"

# DEVELOPMENT ONLY: Disable SSL verification for requests
export PYTHONHTTPSVERIFY=0
export REQUESTS_CA_BUNDLE=""
export CURL_CA_BUNDLE=""
echo "SSL verification disabled for development"

# Find a random available port between 10000 and 65000
function find_available_port() {
    local port=$(( (RANDOM % 55000) + 10000 ))
    if command -v nc &> /dev/null; then
        while nc -z localhost $port 2>/dev/null; do
            port=$(( (RANDOM % 55000) + 10000 ))
        done
    fi
    echo $port
}

# Kill any existing Flask server on the same port
function kill_existing_server() {
    local port=$1
    if command -v lsof &> /dev/null; then
        echo "Checking for existing processes on port ${port}..."
        local pids=$(lsof -ti :${port} 2>/dev/null)
        if [ -n "$pids" ]; then
            echo "Killing existing processes on port ${port}: ${pids}"
            kill -9 $pids 2>/dev/null || true
        fi
    fi
}

# Use PORT from environment variable or find an available port
if [ -z "$PORT" ]; then
    PORT=$(find_available_port)
fi

# Kill any existing process on the same port
kill_existing_server $PORT

# Run the web app with the specified port
echo "Starting web server at http://localhost:${PORT}"
echo -e "\n\033[1;33mWARNING: Running with SSL verification disabled for development only.\nThis is NOT secure for production use.\033[0m\n"
PYTHONHTTPSVERIFY=0 PORT=$PORT python app.py 