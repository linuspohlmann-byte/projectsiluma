#!/bin/bash
# Deploy cleanup service to Railway
# This script helps deploy the cleanup service as a separate Railway service

set -e

echo "🚀 Deploying Cleanup Service to Railway"
echo "======================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check Railway CLI
if ! command -v railway &> /dev/null; then
    echo -e "${RED}❌ Railway CLI not found${NC}"
    echo "Install with: npm i -g @railway/cli"
    exit 1
fi

echo -e "${GREEN}✅ Railway CLI found${NC}"
echo ""

# Service ID from user
SERVICE_ID="841598ff-e5ee-48bd-82c1-43b1533d8cb5"

echo "📋 Service ID: ${SERVICE_ID}"
echo ""

# Check if we need to create a railway.json or use Procfile
if [ -f "Procfile.cleanup" ]; then
    echo "✅ Found Procfile.cleanup"
    echo ""
    echo "📝 To deploy the cleanup service:"
    echo ""
    echo "Option 1: Via Railway Dashboard (Recommended)"
    echo "  1. Go to Railway Dashboard"
    echo "  2. Select your project"
    echo "  3. Click 'New Service' → 'GitHub Repo'"
    echo "  4. Select the same repository"
    echo "  5. In the service settings:"
    echo "     - Set 'Root Directory' to: . (current directory)"
    echo "     - Set 'Start Command' to: python cleanup_service.py"
    echo "     - OR create a Procfile with: web: python cleanup_service.py"
    echo ""
    echo "Option 2: Via Railway CLI"
    echo "  1. Create a railway.json in the root:"
    echo "     {"
    echo "       \"build\": {"
    echo "         \"builder\": \"NIXPACKS\""
    echo "       },"
    echo "       \"deploy\": {"
    echo "         \"startCommand\": \"python cleanup_service.py\""
    echo "       }"
    echo "     }"
    echo ""
    echo "  2. Then deploy:"
    echo "     railway service --id ${SERVICE_ID}"
    echo "     railway up"
    echo ""
    
    # Check if service exists
    echo "🔍 Checking service status..."
    if railway service --id ${SERVICE_ID} 2>&1 | grep -q "not found"; then
        echo -e "${YELLOW}⚠️  Service not found. You may need to create it first.${NC}"
        echo ""
        echo "To create the service:"
        echo "  1. Go to Railway Dashboard"
        echo "  2. Click 'New Service' → 'GitHub Repo'"
        echo "  3. Select your repository"
        echo "  4. Configure it to run cleanup_service.py"
    else
        echo -e "${GREEN}✅ Service found${NC}"
        echo ""
        echo "📦 Deploying cleanup service..."
        railway service --id ${SERVICE_ID}
        railway up
    fi
else
    echo -e "${RED}❌ Procfile.cleanup not found${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo "📝 Next steps:"
echo "  1. Verify DATABASE_URL is set in cleanup service"
echo "  2. Check Railway logs to ensure service started"
echo "  3. Test health endpoint: curl http://<private-domain>/health"
echo "  4. Set CLEANUP_SERVICE_URL in main app service"
echo ""

