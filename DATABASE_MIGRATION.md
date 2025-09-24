# 🗄️ Database Migration Guide

## Problem
Currently using SQLite which gets deleted on every `railway up` deployment, causing all user data to be lost.

## Solution
Migrate to Railway PostgreSQL for persistent data storage.

## Step-by-Step Migration

### 1. Add PostgreSQL to Railway
1. Go to [Railway Dashboard](https://railway.app/dashboard)
2. Select your project
3. Click "New Service" → "Database" → "PostgreSQL"
4. Wait for PostgreSQL to be provisioned

### 2. Connect PostgreSQL to your App
1. In Railway Dashboard, go to your app service
2. Go to "Variables" tab
3. Add new variable: `DATABASE_URL`
4. Copy the PostgreSQL connection string from the PostgreSQL service
5. Paste it as the value for `DATABASE_URL`

### 3. Deploy the Migration
```bash
# Commit the new files
git add .
git commit -m "Add PostgreSQL support and migration script"
git push

# Wait for deployment to complete
# Then run the migration
railway run python migrate_to_postgresql.py
```

### 4. Update Database Code (Optional)
The app will automatically detect PostgreSQL via `DATABASE_URL` and use it instead of SQLite.

### 5. Verify Migration
1. Check that users can login
2. Verify user data is preserved
3. Test that data persists after `railway up`

## Benefits After Migration

✅ **Persistent Data**: User accounts and progress survive deployments
✅ **Scalability**: PostgreSQL can handle more users
✅ **Backups**: Railway provides automatic backups
✅ **Zero Downtime**: Deployments don't affect user data

## Rollback Plan
If something goes wrong:
1. Remove `DATABASE_URL` environment variable
2. App will fall back to SQLite
3. Run setup endpoint to recreate test user

## Testing
After migration, test:
- [ ] User registration
- [ ] User login
- [ ] Progress saving
- [ ] Data persistence after deployment
- [ ] All existing functionality

## Support
If you encounter issues:
1. Check Railway logs
2. Verify `DATABASE_URL` is set correctly
3. Run migration script again if needed
