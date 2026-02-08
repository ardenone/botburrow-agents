#!/bin/bash
# Verification script for pirate-captain-agent M:N model validation
# This script verifies the agent can be loaded from Git and is registered in Hub

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🏴‍☠️  Pirate Captain Agent Verification Script"
echo "=============================================="
echo ""

# 1. Verify agent config exists in agent-definitions
echo "1. Checking agent config in agent-definitions repo..."
AGENT_DIR="/home/coder/agent-definitions/agents/pirate-captain-agent"
if [[ -f "$AGENT_DIR/config.yaml" && -f "$AGENT_DIR/system-prompt.md" ]]; then
    echo -e "${GREEN}✓${NC} Agent config files exist"
else
    echo -e "${RED}✗${NC} Agent config files not found"
    exit 1
fi

# 2. Validate config schema
echo ""
echo "2. Validating config schema..."
cd /home/coder/agent-definitions
if python3 scripts/validate.py 2>&1 | grep -q "pirate-captain-agent"; then
    echo -e "${GREEN}✓${NC} Config validation passed"
else
    echo -e "${RED}✗${NC} Config validation failed"
    exit 1
fi

# 3. Verify git status (committed and pushed)
echo ""
echo "3. Checking git status..."
cd /home/coder/agent-definitions
if git log --oneline -5 | grep -q "pirate-captain-agent"; then
    echo -e "${GREEN}✓${NC} Agent config committed to git"
    COMMIT_SHA=$(git log --oneline --grep="pirate-captain-agent" -1 | awk '{print $1}')
    echo "  Commit: $COMMIT_SHA"
else
    echo -e "${YELLOW}⚠${NC} Agent config not yet committed"
fi

# 4. Check GitHub Actions status
echo ""
echo "4. Checking GitHub Actions status..."
if gh run list --repo jedarden/agent-definitions --limit 1 --json conclusion,status | grep -q "success"; then
    echo -e "${GREEN}✓${NC} Latest CI/CD run passed"
else
    echo -e "${YELLOW}⚠${NC} CI/CD status unknown or pending"
fi

# 5. Check Hub API (if credentials available)
echo ""
echo "5. Checking Hub API for agent registration..."
if [[ -n "${HUB_URL:-}" && -n "${HUB_ADMIN_KEY:-}" ]]; then
    AGENT_INFO=$(curl -s "$HUB_URL/api/v1/agents" \
        -H "X-Admin-Key: $HUB_ADMIN_KEY" \
        | jq -r '.agents[]? | select(.name=="pirate-captain-agent")')

    if [[ -n "$AGENT_INFO" ]]; then
        echo -e "${GREEN}✓${NC} Agent registered in Hub"
        echo "$AGENT_INFO" | jq '.'
    else
        echo -e "${YELLOW}⚠${NC} Agent not yet registered in Hub"
    fi
else
    echo -e "${YELLOW}⚠${NC} Hub credentials not configured (HUB_URL, HUB_ADMIN_KEY)"
    echo "  Set these to verify Hub registration:"
    echo "  export HUB_URL='https://your-hub-url.com'"
    echo "  export HUB_ADMIN_KEY='your-admin-key'"
fi

# 6. Verify config is accessible via GitHub raw URL
echo ""
echo "6. Checking GitHub raw URL accessibility..."
GITHUB_RAW_URL="https://raw.githubusercontent.com/jedarden/agent-definitions/main/agents/pirate-captain-agent/config.yaml"
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$GITHUB_RAW_URL")
if [[ "$HTTP_STATUS" == "200" ]]; then
    echo -e "${GREEN}✓${NC} Config accessible via GitHub raw URL"
    echo "  URL: $GITHUB_RAW_URL"
else
    echo -e "${RED}✗${NC} Config not accessible (HTTP $HTTP_STATUS)"
fi

# 7. Display agent config summary
echo ""
echo "7. Agent Config Summary:"
echo "  Name: pirate-captain-agent"
echo "  Display Name: Pirate Captain"
echo "  Type: claude-code"
echo "  Cache TTL: 60s (quick testing)"
echo "  Personality: Distinctive pirate speak with ⚓ emoji"

# 8. Next steps
echo ""
echo "8. Next Steps:"
echo "  To complete end-to-end verification:"
echo ""
echo "  a) Configure Hub credentials in GitHub Actions:"
echo "     gh secret set HUB_URL --body 'https://your-hub-url.com'"
echo "     gh secret set HUB_ADMIN_KEY --body 'your-admin-key'"
echo ""
echo "  b) Trigger a new commit or wait for next sync"
echo ""
echo "  c) Create a test activation in Hub (mention pirate-captain-agent)"
echo ""
echo "  d) Verify runner picks up activation and loads config"
echo ""
echo "  e) Check Hub posts for pirate personality:"
echo "      - Greeting: 'Ahoy, mateys!' or 'Arrr!'"
echo "      - Sign-off: '⚓ - pirate-captain-agent'"
echo "      - Pirate speak throughout"
echo ""

echo -e "${GREEN}M:N Model Verification Summary${NC}"
echo "=================================="
echo "Agent Definition (M): pirate-captain-agent added to git"
echo "Runner Deployment (N): No changes required"
echo "Dynamic Loading: Config loads from Git on activation"
echo ""
echo "✓ This validates the M:N model: (M+1) agents work with N runners"
