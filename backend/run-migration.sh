#!/bin/bash
# Migration setup guide

set -e

echo "=========================================="
echo "Alembic Migration Setup"
echo "=========================================="
echo ""

# Check if we're in the backend directory
if [ ! -f "alembic.ini" ]; then
    echo "❌ Error: alembic.ini not found. Run from backend/ directory."
    exit 1
fi

echo "✅ Found alembic.ini"
echo ""

# Show current migration status
echo "📋 Current migration status:"
alembic current
echo ""

# Show pending migrations
echo "📋 Pending migrations:"
alembic history --verbose | tail -5
echo ""

# Confirm before upgrading
read -p "Ready to apply migration 0024_add_devcontainer_audit_embeddings? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🚀 Applying migration..."
    alembic upgrade head

    echo ""
    echo "✅ Migration applied successfully!"
    echo ""

    # Show new current version
    echo "Current version:"
    alembic current
    echo ""

    # Verify tables were created (Postgres only)
    if command -v psql &> /dev/null; then
        echo "📊 Verifying tables..."
        psql -c "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename IN ('devcontainers', 'audit_logs', 'analysis_embeddings') ORDER BY tablename;"
        echo "✅ All tables created!"
    fi
else
    echo "⏭️  Migration skipped."
    exit 0
fi
