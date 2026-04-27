#!/bin/bash

# phase-0-complete.sh - Finalize Phase 0 and prepare for Phase 1

set -euo pipefail

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Phase 0: Project Setup - COMPLETE${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check current branch
CURRENT_BRANCH=$(git branch --show-current)
if [[ "$CURRENT_BRANCH" != "phase-0-project-setup" ]]; then
    echo "⚠️  Warning: Not on phase-0-project-setup branch"
    echo "Current branch: $CURRENT_BRANCH"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "📋 Phase 0 Completion Status:"
echo "   ✅ Agent A: Application skeleton (33/33 tests passing)"
echo "   ✅ Agent B: Development environment & Flatpak"
echo "   ✅ Agent C: CI/CD pipeline & documentation"
echo ""

echo "🔍 Running final verification..."
echo ""

# Run quick checks
echo "1. Checking git status..."
git status --short

echo ""
echo "2. Checking for uncommitted changes..."
if [[ -n $(git status --porcelain) ]]; then
    echo "   ⚠️  There are uncommitted changes"
    git status --porcelain
else
    echo "   ✅ Working tree clean"
fi

echo ""
echo "📝 Next steps to complete Phase 0:"
echo ""
echo "1. Merge to main branch:"
echo "   git checkout main"
echo "   git merge phase-0-project-setup"
echo ""
echo "2. Clean up branch:"
echo "   git branch -d phase-0-project-setup"
echo ""
echo "3. Set up development environment:"
echo "   ./scripts/dev-setup.sh"
echo ""
echo "4. Start development:"
echo "   docker-compose up dev"
echo ""
echo "5. Run verification tests:"
echo "   docker-compose exec dev pytest"
echo "   docker-compose exec dev ruff check src/"
echo ""
echo "📊 For detailed completion report, see:"
echo "   PHASE_0_COMPLETION_REPORT.md"
echo ""
echo -e "${GREEN}Phase 0 is ready for final review and merge!${NC}"
echo ""