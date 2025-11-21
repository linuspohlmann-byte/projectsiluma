#!/bin/bash
# Deploy cleanup service immediately
set -e

echo "🚀 Deploying Cleanup Service..."

# Get DATABASE_URL from main app
DB_URL=$(railway variables --service projectsiluma 2>&1 | grep "DATABASE_URL" | head -1 | sed 's/.*│ //' | sed 's/ │.*//' | tr -d ' ')

if [ -z "$DB_URL" ]; then
    echo "❌ Could not get DATABASE_URL. Please set it manually in Railway Dashboard."
    exit 1
fi

echo "✅ Found DATABASE_URL"

# Service ID
SERVICE_ID="841598ff-e5ee-48bd-82c1-43b1533d8cb5"

# Try to deploy
echo "📦 Deploying service..."
railway up --service-id "$SERVICE_ID" 2>&1 || {
    echo "⚠️  Could not deploy via CLI. Please deploy manually:"
    echo "   1. Go to Railway Dashboard"
    echo "   2. Select service with ID: $SERVICE_ID"
    echo "   3. Click 'Deploy' or push to GitHub"
    echo ""
    echo "Then set these variables in the service:"
    echo "   DATABASE_URL=$DB_URL"
}

echo "✅ Done!"

