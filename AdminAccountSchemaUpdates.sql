-- Admin session security fields
ALTER TABLE admin_accounts ADD COLUMN IF NOT EXISTS session_fingerprint TEXT;
ALTER TABLE admin_accounts ADD COLUMN IF NOT EXISTS force_reauth_at TIMESTAMPTZ;
ALTER TABLE admin_accounts ADD COLUMN IF NOT EXISTS last_ip TEXT;
ALTER TABLE admin_accounts ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ;

-- Staff roles / statuses
ALTER TABLE admin_accounts ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'applicant';
ALTER TABLE admin_accounts ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'pending';
ALTER TABLE admin_accounts ADD COLUMN IF NOT EXISTS hired_at TIMESTAMPTZ;
ALTER TABLE admin_accounts ADD COLUMN IF NOT EXISTS hired_by BIGINT;
ALTER TABLE admin_accounts ADD COLUMN IF NOT EXISTS rules_accepted_at TIMESTAMPTZ;
ALTER TABLE admin_accounts ADD COLUMN IF NOT EXISTS rules_version INT NOT NULL DEFAULT 1;
ALTER TABLE admin_accounts ADD COLUMN IF NOT EXISTS payout_type TEXT;
ALTER TABLE admin_accounts ADD COLUMN IF NOT EXISTS payout_details TEXT;

ALTER TABLE admin_accounts DROP CONSTRAINT IF EXISTS admin_accounts_role_check;
ALTER TABLE admin_accounts ADD CONSTRAINT admin_accounts_role_check
    CHECK (role IN ('owner', 'senior_admin', 'junior_admin', 'moderator', 'applicant', 'suspended'));

ALTER TABLE admin_accounts DROP CONSTRAINT IF EXISTS admin_accounts_status_check;
ALTER TABLE admin_accounts ADD CONSTRAINT admin_accounts_status_check
    CHECK (status IN ('active', 'pending', 'rejected', 'suspended'));
