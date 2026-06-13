# app.py - Main application file
import os
import re
import uuid
from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import func, desc

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'campus-placement-secret-key-2024'
#app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///campus_placement.db'
database_url = os.environ.get("DATABASE_URL")

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://",
        "postgresql://",
        1
    )

app.config['SQLALCHEMY_DATABASE_URI'] = (
    database_url or 'sqlite:///campus_placement.db'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

# ------------------------- Database Models -------------------------
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'student', 'company', 'admin'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class StudentProfile(db.Model):
    __tablename__ = 'student_profiles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)
    full_name = db.Column(db.String(100), nullable=False)
    roll_number = db.Column(db.String(50), unique=True)
    branch = db.Column(db.String(50))
    cgpa = db.Column(db.Float)
    passing_year = db.Column(db.Integer)
    phone = db.Column(db.String(15))
    skills = db.Column(db.Text)  # Comma separated skills
    resume_text = db.Column(db.Text)  # Extracted text from resume
    
    user = db.relationship('User', backref='student_profile', uselist=False)
    applications = db.relationship('JobApplication', backref='student', lazy=True)

class CompanyProfile(db.Model):
    __tablename__ = 'company_profiles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)
    company_name = db.Column(db.String(100), nullable=False)
    industry = db.Column(db.String(50))
    description = db.Column(db.Text)
    website = db.Column(db.String(200))
    location = db.Column(db.String(100))
    
    user = db.relationship('User', backref='company_profile', uselist=False)
    jobs = db.relationship('JobPost', backref='company', lazy=True)

class JobPost(db.Model):
    __tablename__ = 'job_posts'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company_profiles.id'))
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    required_skills = db.Column(db.Text)  # Comma separated
    location = db.Column(db.String(100))
    salary_range = db.Column(db.String(50))
    last_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    applications = db.relationship('JobApplication', backref='job', lazy=True)

class JobApplication(db.Model):
    __tablename__ = 'job_applications'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student_profiles.id'))
    job_id = db.Column(db.Integer, db.ForeignKey('job_posts.id'))
    applied_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='Applied')  # Applied, Shortlisted, Rejected, Placed
    screening_score = db.Column(db.Float, default=0.0)
    remarks = db.Column(db.Text)

class PlacementRecord(db.Model):
    __tablename__ = 'placement_records'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student_profiles.id'))
    job_id = db.Column(db.Integer, db.ForeignKey('job_posts.id'))
    company_id = db.Column(db.Integer, db.ForeignKey('company_profiles.id'))
    package = db.Column(db.String(50))
    joining_date = db.Column(db.Date)
    placed_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    student = db.relationship('StudentProfile')
    job = db.relationship('JobPost')
    company = db.relationship('CompanyProfile')

# ------------------------- Helper Functions -------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please login first', 'warning')
                return redirect(url_for('login'))
            user = User.query.get(session['user_id'])
            if user.role not in roles:
                flash('You do not have permission to access this page', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def extract_text_from_resume(file):
    """Extract text from uploaded resume file (txt or pdf)"""
    filename = file.filename
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    text = ""
    
    if ext == 'txt':
        text = file.read().decode('utf-8')
    elif ext == 'pdf':
        try:
            import PyPDF2
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() or ""
        except ImportError:
            text = "PDF processing requires PyPDF2. Please install: pip install PyPDF2"
        except Exception as e:
            text = f"Error reading PDF: {str(e)}"
    else:
        text = "Unsupported file format. Please upload TXT or PDF."
    
    return text.lower()

def calculate_screening_score(resume_text, job_skills):
    """Calculate match percentage between resume text and job required skills"""
    if not resume_text or not job_skills:
        return 0.0
    
    resume_text = resume_text.lower()
    skills_list = [s.strip().lower() for s in job_skills.split(',') if s.strip()]
    if not skills_list:
        return 100.0
    
    matched = sum(1 for skill in skills_list if skill in resume_text)
    return (matched / len(skills_list)) * 100

# ------------------------- Routes -------------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['user_role'] = user.role
            session['user_email'] = user.email
            flash(f'Welcome back!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

@app.route('/register/student', methods=['GET', 'POST'])
def register_student():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        roll_number = request.form.get('roll_number')
        branch = request.form.get('branch')
        cgpa = request.form.get('cgpa')
        passing_year = request.form.get('passing_year')
        phone = request.form.get('phone')
        skills = request.form.get('skills')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('register_student'))
        
        user = User(email=email, role='student')
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        
        student = StudentProfile(
            user_id=user.id,
            full_name=full_name,
            roll_number=roll_number,
            branch=branch,
            cgpa=float(cgpa) if cgpa else None,
            passing_year=int(passing_year) if passing_year else None,
            phone=phone,
            skills=skills
        )
        db.session.add(student)
        db.session.commit()
        
        flash('Registration successful! Please login', 'success')
        return redirect(url_for('login'))
    return render_template('register_student.html')

@app.route('/register/company', methods=['GET', 'POST'])
def register_company():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        company_name = request.form.get('company_name')
        industry = request.form.get('industry')
        description = request.form.get('description')
        website = request.form.get('website')
        location = request.form.get('location')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('register_company'))
        
        user = User(email=email, role='company')
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        
        company = CompanyProfile(
            user_id=user.id,
            company_name=company_name,
            industry=industry,
            description=description,
            website=website,
            location=location
        )
        db.session.add(company)
        db.session.commit()
        
        flash('Company registration successful! Please login', 'success')
        return redirect(url_for('login'))
    return render_template('register_company.html')

@app.route('/dashboard')
@login_required
def dashboard():
    user = User.query.get(session['user_id'])
    if user.role == 'student':
        return redirect(url_for('student_dashboard'))
    elif user.role == 'company':
        return redirect(url_for('company_dashboard'))
    else:
        return redirect(url_for('admin_dashboard'))

# ------------------------- Student Dashboard -------------------------
@app.route('/student/dashboard')
@login_required
@role_required('student')
def student_dashboard():
    student = StudentProfile.query.filter_by(user_id=session['user_id']).first()
    applications = JobApplication.query.filter_by(student_id=student.id).all()
    
    # Statistics
    total_applications = len(applications)
    shortlisted = sum(1 for a in applications if a.status == 'Shortlisted')
    placed = sum(1 for a in applications if a.status == 'Placed')
    
    # Active jobs (not applied yet)
    applied_job_ids = [a.job_id for a in applications]
    active_jobs = JobPost.query.filter(
        JobPost.is_active == True,
        JobPost.id.notin_(applied_job_ids) if applied_job_ids else True
    ).all()
    
    return render_template('student_dashboard.html', 
                         student=student, 
                         applications=applications,
                         active_jobs=active_jobs,
                         total_applications=total_applications,
                         shortlisted=shortlisted,
                         placed=placed)

@app.route('/student/upload_resume', methods=['POST'])
@login_required
@role_required('student')
def upload_resume():
    student = StudentProfile.query.filter_by(user_id=session['user_id']).first()
    if 'resume' not in request.files:
        flash('No file selected', 'danger')
        return redirect(url_for('student_dashboard'))
    
    file = request.files['resume']
    if file.filename == '':
        flash('No file selected', 'danger')
        return redirect(url_for('student_dashboard'))
    
    if file:
        filename = secure_filename(f"{student.id}_{uuid.uuid4().hex}_{file.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Extract text from resume
        file.seek(0)  # Reset file pointer
        extracted_text = extract_text_from_resume(file)
        
        student.resume_text = extracted_text
        db.session.commit()
        
        flash('Resume uploaded and processed successfully!', 'success')
    return redirect(url_for('student_dashboard'))

@app.route('/student/apply/<int:job_id>')
@login_required
@role_required('student')
def apply_job(job_id):
    student = StudentProfile.query.filter_by(user_id=session['user_id']).first()
    job = JobPost.query.get_or_404(job_id)
    
    # Check if already applied
    existing = JobApplication.query.filter_by(student_id=student.id, job_id=job_id).first()
    if existing:
        flash('You have already applied for this job', 'warning')
        return redirect(url_for('student_dashboard'))
    
    # Calculate screening score
    score = calculate_screening_score(student.resume_text or '', job.required_skills or '')
    
    application = JobApplication(
        student_id=student.id,
        job_id=job_id,
        screening_score=score,
        status='Applied'
    )
    db.session.add(application)
    db.session.commit()
    
    flash(f'Applied successfully! Screening score: {score:.1f}%', 'success')
    return redirect(url_for('student_dashboard'))

@app.route('/student/withdraw/<int:app_id>')
@login_required
@role_required('student')
def withdraw_application(app_id):
    application = JobApplication.query.get_or_404(app_id)
    student = StudentProfile.query.filter_by(user_id=session['user_id']).first()
    
    if application.student_id != student.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('student_dashboard'))
    
    if application.status == 'Applied':
        db.session.delete(application)
        db.session.commit()
        flash('Application withdrawn successfully', 'success')
    else:
        flash('Cannot withdraw application at this stage', 'warning')
    
    return redirect(url_for('student_dashboard'))

# ------------------------- Company Dashboard -------------------------
@app.route('/company/dashboard')
@login_required
@role_required('company')
def company_dashboard():
    company = CompanyProfile.query.filter_by(user_id=session['user_id']).first()
    jobs = JobPost.query.filter_by(company_id=company.id).all()
    
    total_jobs = len(jobs)
    total_applications = sum(len(job.applications) for job in jobs)
    
    return render_template('company_dashboard.html', 
                         company=company, 
                         jobs=jobs,
                         total_jobs=total_jobs,
                         total_applications=total_applications)

@app.route('/company/post_job', methods=['GET', 'POST'])
@login_required
@role_required('company')
def post_job():
    company = CompanyProfile.query.filter_by(user_id=session['user_id']).first()
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        required_skills = request.form.get('required_skills')
        location = request.form.get('location')
        salary_range = request.form.get('salary_range')
        last_date_str = request.form.get('last_date')
        
        last_date = datetime.strptime(last_date_str, '%Y-%m-%d').date() if last_date_str else None
        
        job = JobPost(
            company_id=company.id,
            title=title,
            description=description,
            required_skills=required_skills,
            location=location,
            salary_range=salary_range,
            last_date=last_date
        )
        db.session.add(job)
        db.session.commit()
        
        flash('Job posted successfully!', 'success')
        return redirect(url_for('company_dashboard'))
    
    return render_template('post_job.html')

@app.route('/company/job/<int:job_id>/applications')
@login_required
@role_required('company')
def view_applications(job_id):
    company = CompanyProfile.query.filter_by(user_id=session['user_id']).first()
    job = JobPost.query.filter_by(id=job_id, company_id=company.id).first_or_404()
    
    return render_template('view_applications.html', job=job, applications=job.applications)

@app.route('/company/application/<int:app_id>/update', methods=['POST'])
@login_required
@role_required('company')
def update_application_status(app_id):
    application = JobApplication.query.get_or_404(app_id)
    company = CompanyProfile.query.filter_by(user_id=session['user_id']).first()
    
    # Verify ownership
    if application.job.company_id != company.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('company_dashboard'))
    
    new_status = request.form.get('status')
    remarks = request.form.get('remarks', '')
    
    if new_status in ['Shortlisted', 'Rejected', 'Placed']:
        application.status = new_status
        application.remarks = remarks
        db.session.commit()
        
        # If placed, create placement record
        if new_status == 'Placed':
            existing = PlacementRecord.query.filter_by(student_id=application.student_id, job_id=application.job_id).first()
            if not existing:
                placement = PlacementRecord(
                    student_id=application.student_id,
                    job_id=application.job_id,
                    company_id=company.id,
                    package=application.job.salary_range,
                    joining_date=datetime.now().date()
                )
                db.session.add(placement)
                db.session.commit()
        
        flash(f'Application status updated to {new_status}', 'success')
    else:
        flash('Invalid status', 'danger')
    
    return redirect(url_for('view_applications', job_id=application.job_id))

@app.route('/company/run_screening/<int:job_id>')
@login_required
@role_required('company')
def run_screening(job_id):
    company = CompanyProfile.query.filter_by(user_id=session['user_id']).first()
    job = JobPost.query.filter_by(id=job_id, company_id=company.id).first_or_404()
    
    # Update screening scores for all applications
    for app in job.applications:
        score = calculate_screening_score(app.student.resume_text or '', job.required_skills or '')
        app.screening_score = score
    
    db.session.commit()
    flash(f'Screening scores updated for {len(job.applications)} applicants', 'success')
    
    return redirect(url_for('view_applications', job_id=job_id))

# ------------------------- Admin Dashboard -------------------------
@app.route('/admin/dashboard')
@login_required
@role_required('admin')
def admin_dashboard():
    # Statistics
    total_students = StudentProfile.query.count()
    total_companies = CompanyProfile.query.count()
    total_jobs = JobPost.query.count()
    total_applications = JobApplication.query.count()
    total_placements = PlacementRecord.query.count()
    
    # Placement analytics data
    placed_students = PlacementRecord.query.all()
    placed_count = len(placed_students)
    student_count = total_students if total_students > 0 else 1
    placement_percentage = (placed_count / student_count) * 100
    
    # Branch wise placement
    branch_stats = db.session.query(
        StudentProfile.branch, 
        func.count(PlacementRecord.id).label('placed_count')
    ).outerjoin(PlacementRecord, StudentProfile.id == PlacementRecord.student_id)\
     .group_by(StudentProfile.branch).all()
    
    branch_labels = [stat[0] or 'Unknown' for stat in branch_stats]
    branch_data = [stat[1] for stat in branch_stats]
    
    # Recent placements
    recent_placements = PlacementRecord.query.order_by(desc(PlacementRecord.placed_date)).limit(10).all()
    
    # Company wise hiring
    company_stats = db.session.query(
        CompanyProfile.company_name,
        func.count(PlacementRecord.id).label('hired_count')
    ).join(PlacementRecord, CompanyProfile.id == PlacementRecord.company_id)\
     .group_by(CompanyProfile.company_name).order_by(desc('hired_count')).limit(5).all()
    
    return render_template('admin_dashboard.html',
                         total_students=total_students,
                         total_companies=total_companies,
                         total_jobs=total_jobs,
                         total_applications=total_applications,
                         placement_percentage=placement_percentage,
                         placed_count=placed_count,
                         branch_labels=branch_labels,
                         branch_data=branch_data,
                         recent_placements=recent_placements,
                         company_stats=company_stats)

@app.route('/admin/students')
@login_required
@role_required('admin')
def admin_students():
    students = StudentProfile.query.all()
    return render_template('admin_students.html', students=students)

@app.route('/admin/companies')
@login_required
@role_required('admin')
def admin_companies():
    companies = CompanyProfile.query.all()
    return render_template('admin_companies.html', companies=companies)

@app.route('/admin/jobs')
@login_required
@role_required('admin')
def admin_jobs():
    jobs = JobPost.query.all()
    return render_template('admin_jobs.html', jobs=jobs)

@app.route('/admin/placements')
@login_required
@role_required('admin')
def admin_placements():
    placements = PlacementRecord.query.all()
    return render_template('admin_placements.html', placements=placements)

@app.route('/admin/delete_user/<int:user_id>')
@login_required
@role_required('admin')
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == 'admin':
        flash('Cannot delete admin user', 'danger')
    else:
        db.session.delete(user)
        db.session.commit()
        flash(f'User {user.email} deleted successfully', 'success')
    return redirect(request.referrer or url_for('admin_dashboard'))

# ------------------------- Create admin user if not exists -------------------------
def init_db():
    with app.app_context():
        db.create_all()
        # Create admin user if not exists
        admin = User.query.filter_by(role='admin').first()
        if not admin:
            admin = User(email='admin@campus.com', role='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("Admin user created: admin@campus.com / admin123")
        
        # Create demo student if none exists
        if StudentProfile.query.count() == 0:
            demo_student_user = User(email='student@demo.com', role='student')
            demo_student_user.set_password('student123')
            db.session.add(demo_student_user)
            db.session.flush()
            
            demo_student = StudentProfile(
                user_id=demo_student_user.id,
                full_name='John Doe',
                roll_number='CS2024001',
                branch='Computer Science',
                cgpa=8.5,
                passing_year=2025,
                phone='9876543210',
                skills='Python, Java, SQL, Machine Learning',
                resume_text='python java sql machine learning data structures algorithms web development'
            )
            db.session.add(demo_student)
            
            # Demo company
            demo_company_user = User(email='company@demo.com', role='company')
            demo_company_user.set_password('company123')
            db.session.add(demo_company_user)
            db.session.flush()
            
            demo_company = CompanyProfile(
                user_id=demo_company_user.id,
                company_name='Tech Solutions Inc.',
                industry='Information Technology',
                description='Leading IT services company',
                website='www.techsolutions.com',
                location='Bangalore'
            )
            db.session.add(demo_company)
            db.session.flush()
            
            # Demo job
            demo_job = JobPost(
                company_id=demo_company.id,
                title='Software Engineer Intern',
                description='Looking for passionate software engineering interns',
                required_skills='Python, Java, SQL',
                location='Bangalore',
                salary_range='5-8 LPA',
                last_date=datetime(2025, 12, 31).date(),
                is_active=True
            )
            db.session.add(demo_job)
            db.session.commit()
            print("Demo data created successfully")

# ------------------------- Run App -------------------------
with app.app_context():
    init_db()

if __name__ == '__main__':
    #app.run(debug=True, host='0.0.0.0', port=5000)
    app.run(debug=True)