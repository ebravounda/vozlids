# Auth testing
- Admin: admin@vozlead.es / VozLead2026! (seeded on startup)
- Login: POST /api/auth/login → user + access_token, sets httpOnly cookies access_token / refresh_token
- GET /api/auth/me with cookies or `Authorization: Bearer <token>`
- 5 failed logins for same ip:email → 429 for 15 min
- Mongo: users.email unique index, bcrypt hash starts with $2b$
