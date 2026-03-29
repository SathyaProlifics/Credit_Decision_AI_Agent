-- ============================================================
-- OrchestrateAI Credit Decision Agent – database initialisation
-- Run once after RDS is provisioned (Terraform does this automatically)
-- Manual run: mysql -h <host> -u admin -p dev < terraform/init_db.sql
-- ============================================================

-- Use the target database
-- (already selected via the -d / connection string in Terraform local-exec)

CREATE TABLE IF NOT EXISTS credit_applications (
    id                 INT           PRIMARY KEY AUTO_INCREMENT,

    -- Applicant personal info
    applicant_name     VARCHAR(255),
    applicant_dob      DATE,
    age                INT,
    email              VARCHAR(255),

    -- Financial profile
    income             DECIMAL(15,2),
    employment_status  VARCHAR(50),
    credit_score       INT,
    dti_ratio          DECIMAL(5,4),
    existing_debts     DECIMAL(15,2),
    requested_credit   DECIMAL(15,2),

    -- Application metadata
    source             VARCHAR(50),              -- 'web', 'api', etc.
    application_status VARCHAR(50),              -- PENDING | PROCESSING | APPROVED | DENIED | REFER | ERROR
    reason             TEXT,                     -- Plain-text explanation from AI decision
    confidence         INT,                      -- 0-100 confidence score from DecisionMaker

    -- Full agent pipeline output (JSON blob from all 4 agents)
    agent_output       LONGTEXT,

    -- Timestamps
    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Indexes for common queries
    INDEX idx_status    (application_status),
    INDEX idx_applicant (applicant_name),
    INDEX idx_created   (created_at),
    INDEX idx_email     (email)
);
