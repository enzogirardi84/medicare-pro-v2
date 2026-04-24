#!/bin/bash
#
# Pre-commit hook para Medicare Pro
# Instalar: cp scripts/pre-commit-check.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
#

set -e

echo "🔍 Running pre-commit checks..."

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

FAILED=0

# Check Python syntax
echo "📋 Checking Python syntax..."
if ! python -m py_compile core/*.py views/*.py 2>/dev/null; then
    echo -e "${RED}❌ Python syntax errors found${NC}"
    FAILED=1
else
    echo -e "${GREEN}✓ Python syntax OK${NC}"
fi

# Run ruff if available
if command -v ruff &> /dev/null; then
    echo "🔍 Running Ruff linter..."
    if ! ruff check core/ views/ tests/ --quiet 2>/dev/null; then
        echo -e "${YELLOW}⚠️  Ruff found issues (non-blocking)${NC}"
    else
        echo -e "${GREEN}✓ Ruff passed${NC}"
    fi
fi

# Check for except: pass patterns (forbidden)
echo "🔒 Checking for silent error handling..."
if grep -r "except.*:.*pass" core/ views/ --include="*.py" 2>/dev/null | grep -v "Intencional" | head -5; then
    echo -e "${RED}❌ Found 'except: pass' without proper handling!${NC}"
    echo "   Add logging or comment '# Intencional' if needed."
    FAILED=1
else
    echo -e "${GREEN}✓ No silent error handling found${NC}"
fi

# Check for hardcoded secrets
echo "🔐 Checking for hardcoded secrets..."
if grep -rE "(password|secret|key|token)\s*=\s*[\"'][^\"']+[\"']" core/ views/ --include="*.py" 2>/dev/null | grep -v "getenv\|os.environ\|settings\." | head -5; then
    echo -e "${YELLOW}⚠️  Potential hardcoded secrets found (review manually)${NC}"
else
    echo -e "${GREEN}✓ No obvious hardcoded secrets${NC}"
fi

# Run tests if pytest available
if command -v pytest &> /dev/null; then
    echo "🧪 Running quick tests..."
    if ! pytest tests/ -x -q --tb=short 2>/dev/null; then
        echo -e "${RED}❌ Tests failed${NC}"
        FAILED=1
    else
        echo -e "${GREEN}✓ Tests passed${NC}"
    fi
fi

if [ $FAILED -eq 1 ]; then
    echo ""
    echo -e "${RED}❌ Pre-commit checks failed!${NC}"
    echo "Fix the issues above before committing."
    exit 1
else
    echo ""
    echo -e "${GREEN}✅ All pre-commit checks passed!${NC}"
    exit 0
fi
