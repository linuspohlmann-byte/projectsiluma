-- Create test user for ProjectSiluma
-- Run this in Railway PostgreSQL console

-- Check if test user already exists
SELECT id, username, email FROM users WHERE username = 'testuser';

-- If no user exists, create one
INSERT INTO users (username, email, password_hash, created_at, is_active, native_language)
VALUES (
    'testuser', 
    'test@example.com', 
    'ef92b778bafe771e89245b89ecbc08a44a4e166c06659911881f383d4473e94f', -- SHA256 of 'password123'
    CURRENT_TIMESTAMP, 
    TRUE, 
    'en'
)
ON CONFLICT (username) DO NOTHING;

-- Verify the user was created
SELECT id, username, email, created_at FROM users WHERE username = 'testuser';
