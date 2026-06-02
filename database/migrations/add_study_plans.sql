CREATE TABLE IF NOT EXISTS study_plans (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  plan_type VARCHAR(20) DEFAULT 'guided',
  status VARCHAR(20) DEFAULT 'active',
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  target_score INTEGER NOT NULL,
  total_days INTEGER NOT NULL,
  total_sessions INTEGER NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS study_plan_days (
  id SERIAL PRIMARY KEY,
  plan_id INTEGER REFERENCES study_plans(id) ON DELETE CASCADE,
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  day_number INTEGER NOT NULL,
  date DATE NOT NULL,
  phase VARCHAR(20) NOT NULL,
  topic VARCHAR(100) NOT NULL,
  difficulty VARCHAR(20) NOT NULL,
  session_type VARCHAR(30) NOT NULL,
  questions_count INTEGER DEFAULT 5,
  is_completed BOOLEAN DEFAULT FALSE,
  score_achieved REAL,
  next_review_date DATE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE interview_profiles
ADD COLUMN IF NOT EXISTS plan_type VARCHAR(10) DEFAULT NULL,
ADD COLUMN IF NOT EXISTS plan_generated_at TIMESTAMP DEFAULT NULL;
