#!/bin/bash
# Pre-deploy syntax check script
# Run this before deploying to catch syntax errors early

set -e

echo "🔍 Running pre-deploy syntax checks..."

# Check Python syntax for all Python files
echo "📝 Checking Python syntax..."
find . -name "*.py" -not -path "./.venv/*" -not -path "./venv/*" -not -path "./node_modules/*" | while read file; do
    if python3 -m py_compile "$file" 2>&1; then
        echo "  ✅ $file"
    else
        echo "  ❌ $file - Syntax error!"
        exit 1
    fi
done

echo "✅ All syntax checks passed!"
echo "🚀 Ready to deploy!"

