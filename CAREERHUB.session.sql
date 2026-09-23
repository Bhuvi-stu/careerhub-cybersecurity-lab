SELECT name
FROM sqlite_master;

SELECT id, name, email, role, created_at
FROM users;

SELECT id, title, company, location, salary
FROM jobs;

SELECT id, user_id, phone, skills, bio
FROM profiles;

SELECT id, user_id, job_id, status
FROM applications;

SELECT id, user_id, job_id, resume, status, created_at
FROM applications;

SELECT * FROM profiles;
