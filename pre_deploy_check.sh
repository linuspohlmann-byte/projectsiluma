#!/bin/bash
# Pre-deploy syntax check script
# Run this before deploying to catch syntax errors early

set -e

echo "🔍 Running pre-deploy syntax checks..."

# Check Python syntax for all Python files
echo "📝 Checking Python syntax..."
ERRORS_FOUND=0

while IFS= read -r file; do
    if python3 -m py_compile "$file" 2>&1; then
        echo "  ✅ $file"
    else
        echo "  ❌ $file - Syntax error!"
        ERRORS_FOUND=1
    fi
done < <(find . -name "*.py" -not -path "./.venv/*" -not -path "./venv/*" -not -path "./node_modules/*" -not -path "./.git/*")

if [ $ERRORS_FOUND -ne 0 ]; then
    echo "❌ Found syntax error(s). Please fix before deploying."
    exit 1
fi

echo "✅ All syntax checks passed!"
echo "🚀 Ready to deploy!"

