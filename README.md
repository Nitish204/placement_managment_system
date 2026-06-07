# 🎓 Campus Placement Management System

A comprehensive web-based platform to streamline campus recruitment processes. It connects students, companies, and placement officers with features like job applications, AI-powered resume screening, application tracking, and real-time placement analytics.

## ✨ Features

- **Student Portal**
  - Register and manage profile (academic details, skills)
  - Upload resume (PDF/TXT) with automatic text extraction
  - Browse and apply for active job postings
  - Track application status (Applied → Shortlisted → Placed/Rejected)
  - View AI-generated screening score for each application

- **Company Portal**
  - Register and manage company profile
  - Post job openings with required skills and description
  - View applicants with their details and screening scores
  - Run one-click AI resume screening based on job skill requirements
  - Update application status (Shortlist, Reject, Place)

- **Admin Dashboard**
  - Complete oversight of students, companies, and job posts
  - Bulk upload students via CSV file
  - Generate random student data for testing (up to 50+)
  - Placement analytics with interactive charts (branch-wise, company-wise)
  - Track placement records and overall placement percentage

- **Security & Analytics**
  - Password hashing using Werkzeug
  - Role-based access control (student / company / admin)
  - Session management
  - Real-time placement statistics and charts (Chart.js)

## 🛠️ Tech Stack

| Layer       | Technology                          |
|-------------|-------------------------------------|
| Backend     | Python 3.11, Flask                  |
| Database    | SQLite (development), PostgreSQL (production-ready) |
| Frontend    | HTML5, CSS3, Bootstrap 5, JavaScript, Chart.js |
| Authentication | Werkzeug (password hashing)      |
| File Handling | PyPDF2 (PDF text extraction)      |
| Deployment  | Render / Railway / PythonAnywhere   |
