-- Migration: Add Jenkins pipeline fields
-- Target: pr_pipelines table

ALTER TABLE pr_pipelines ADD COLUMN target_url VARCHAR(500) DEFAULT '';
ALTER TABLE pr_pipelines ADD COLUMN build_info JSON;
ALTER TABLE pr_pipelines ADD COLUMN test_report JSON;
