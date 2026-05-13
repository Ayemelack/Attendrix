#!/bin/bash

echo "🚀 Starting Attendrix Development Server..."
echo

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.11+"
    exit 1
fi

echo "✅ Python found: $(python3 --version)"

# Check if required packages are installed
echo "📦 Checking dependencies..."

packages=("flask" "flask_cors" "firebase_admin" "jwt" "bcrypt" "decouple")

for package in "${packages[@]}"; do
    if ! python3 -c "import $package" &> /dev/null; then
        echo "📥 Installing $package..."
        python3 -m pip install $package
    else
        echo "✅ $package already installed"
    fi
done

echo
echo "🎯 Dependencies check complete!"
echo

# Create uploads directory if it doesn't exist
mkdir -p uploads logs

# Start the server
echo "🌐 Starting Attendrix development server..."
echo "📍 Server will be available at: http://localhost:5000"
echo "🔍 Health check: http://localhost:5000/health"
echo "🧪 API test: http://localhost:5000/api/test"
echo "ℹ️  System info: http://localhost:5000/api/info"
echo
echo "⏹️  Press Ctrl+C to stop the server"
echo

# Set environment variables
export ENVIRONMENT=development
export FLASK_DEBUG=True

python3 app-simple.py
