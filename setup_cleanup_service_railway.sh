#!/bin/bash
# Setup script for Railway Cleanup Service
# This script helps configure the cleanup service on Railway

set -e

echo "🚀 Railway Cleanup Service Setup"
echo "================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo -e "${YELLOW}⚠️  Railway CLI not found${NC}"
    echo "Install it with: npm i -g @railway/cli"
    echo ""
    echo "Alternatively, you can configure manually in the Railway Dashboard:"
    echo "1. Go to your main app service"
    echo "2. Settings → Variables"
    echo "3. Add: CLEANUP_SERVICE_URL=http://cleanup_serivce.railway.internal"
    echo ""
    exit 1
fi

echo -e "${GREEN}✅ Railway CLI found${NC}"
echo ""

# Get project info
echo "📋 Current Railway project:"
railway status
echo ""

# Check if we're in the right project
read -p "Is this the correct project? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Please run: railway link"
    exit 1
fi

echo ""
echo "🔧 Setting up Cleanup Service connection..."
echo ""

# Get the cleanup service private domain
# Note: This might need to be adjusted based on your actual service name
CLEANUP_SERVICE_NAME="cleanup_serivce"
CLEANUP_SERVICE_URL="http://${CLEANUP_SERVICE_NAME}.railway.internal"

echo "Setting CLEANUP_SERVICE_URL=${CLEANUP_SERVICE_URL}"

# Set environment variable in main app service
railway variables set CLEANUP_SERVICE_URL="${CLEANUP_SERVICE_URL}"

echo ""
echo -e "${GREEN}✅ Environment variable set!${NC}"
echo ""
echo "📝 Summary:"
echo "  - CLEANUP_SERVICE_URL=${CLEANUP_SERVICE_URL}"
echo ""
echo "🔍 Next steps:"
echo "  1. Make sure PostgreSQL is connected to cleanup_serivce service"
echo "  2. Verify the cleanup service is running (check Railway logs)"
echo "  3. Test from UI: Login as admin (user ID 2) → Settings → Admin Tools"
echo ""

