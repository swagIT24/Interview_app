-- Migration: add rubric score columns to interview_answers
-- Run once against the opunto database

ALTER TABLE interview_answers
    ADD COLUMN IF NOT EXISTS score_breakdown     JSONB,
    ADD COLUMN IF NOT EXISTS weakest_dimension   VARCHAR(30),
    ADD COLUMN IF NOT EXISTS model_answer_hint   TEXT;
