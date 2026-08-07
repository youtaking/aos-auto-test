-- Migration: Add status column to unit_test_runs
-- Target: unit_test_runs table

ALTER TABLE unit_test_runs ADD COLUMN status VARCHAR(20) DEFAULT 'completed';
