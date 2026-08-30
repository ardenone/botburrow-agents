#!/run/current-system/sw/bin/bash
# Verify Docker Hub `ardenone` login configuration for CI/CD

set -euo pipefail

echo '=== Docker Hub `ardenone` Login Verification ==='
echo ""

# Check GitHub Actions workflow configuration
echo "1. Checking CI/CD workflow configuration..."
if grep -q "username: ardenone" .github/workflows/ci-cd.yml; then
    echo "   ✅ Username configured as 'ardenone'"
else
    echo "   ❌ Username NOT configured as 'ardenone'"
    exit 1
fi

if grep -q "DOCKERHUB_PASSWORD" .github/workflows/ci-cd.yml; then
    echo "   ✅ Workflow references DOCKERHUB_PASSWORD secret"
else
    echo "   ❌ Workflow does NOT reference DOCKERHUB_PASSWORD"
    exit 1
fi

# Check GitHub Secret status (requires gh CLI)
echo ""
echo "2. Checking GitHub Secret status..."
if command -v gh &> /dev/null; then
    if gh secret list --repo ardenone/botburrow-agents 2>/dev/null | grep -q "DOCKERHUB_PASSWORD"; then
        echo "   ✅ DOCKERHUB_PASSWORD secret is set"
        echo "   → CI/CD will push to Docker Hub on next commit to main"
    else
        echo "   ⚠️  DOCKERHUB_PASSWORD secret NOT set"
        echo "   → CI/CD will skip Docker Hub push (GHCR only)"
        echo ""
        echo "   To enable Docker Hub push:"
        echo "   1. Create Docker Hub Access Token at https://hub.docker.com"
        echo "      - Account: ardenone"
        echo "      - Permissions: Read & Write"
        echo "   2. Set the secret:"
        echo "      gh secret set DOCKERHUB_PASSWORD --repo ardenone/botburrow-agents"
    fi
else
    echo "   ⚠️  GitHub CLI (gh) not installed - cannot check secret status"
    echo "   → Verify manually at: https://github.com/ardenone/botburrow-agents/settings/secrets/actions"
fi

# Check local Docker login
echo ""
echo "3. Checking local Docker login..."
if command -v docker &> /dev/null; then
    if [ -f ~/.docker/config.json ]; then
        CURRENT_USER=$(cat ~/.docker/config.json | jq -r '.auths."https://index.docker.io/v1/" // empty' 2>/dev/null | base64 -d 2>/dev/null | cut -d: -f1 2>/dev/null || echo "unknown")
        if [ "$CURRENT_USER" = "ardenone" ]; then
            echo "   ✅ Logged in as 'ardenone'"
        else
            echo "   ⚠️  Logged in as '$CURRENT_USER' (not 'ardenone')"
            echo "   → Local Docker login is OPTIONAL for CI/CD"
        fi
    else
        echo "   ⚠️  Docker config not found"
    fi
else
    echo "   ⚠️  Docker not installed"
fi

# Summary
echo ""
echo "=== Summary ==="
echo "CI/CD Configuration: ✅ Ready"
echo "Required Action: Set DOCKERHUB_PASSWORD GitHub secret"
echo ""
echo "Documentation:"
echo "  - DOCKERHUB_LOGIN_STATUS.md - Complete status and setup guide"
echo "  - docs/docker-hub-ardenone-setup.md - Detailed procedures"
echo "  - docs/DOCKERHUB_SETUP.md - CI/CD integration"
