import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
from flask_mysqldb import MySQL
import pandas as pd
from datetime import datetime, timedelta, date
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import json
import requests
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask import flash
from werkzeug.utils import secure_filename
import uuid


app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
WEATHER_API_KEY = '7ca175b457b01e2281d6891c55fad117' 

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# MySQL configurations
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'root'
app.config['MYSQL_DB'] = 'construction_project_management'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, user_id, username, role):
        self.id = user_id
        self.username = username
        self.role = role

# User loader callback
@login_manager.user_loader
def load_user(user_id):
    cur = get_db_connection()
    cur.execute("SELECT user_id, username, role FROM users WHERE user_id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    if user:
        return User(user['user_id'], user['username'], user['role'])
    return None

# Helper functions
def get_db_connection():
    return mysql.connection.cursor()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_user_role():
    if 'user_id' in session:
        cur = get_db_connection()
        cur.execute("SELECT role FROM users WHERE user_id = %s", (session['user_id'],))
        role = cur.fetchone()['role']
        cur.close()
        return role
    return None

# Routes
@app.route('/')
@login_required
def index():
    return redirect(url_for('dashboard'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        full_name = request.form['full_name']
        email = request.form['email']
        role = request.form['role']
        
        # Validate inputs
        if not all([username, password, confirm_password, full_name, email]):
            return render_template('register.html', error='All fields are required')
        
        if password != confirm_password:
            return render_template('register.html', error='Passwords do not match')
        
        if len(password) < 8:
            return render_template('register.html', error='Password must be at least 8 characters')
        
        # Check if username or email already exists
        cur = get_db_connection()
        cur.execute("SELECT * FROM users WHERE username = %s OR email = %s", (username, email))
        existing_user = cur.fetchone()
        
        if existing_user:
            cur.close()
            return render_template('register.html', error='Username or email already exists')
        
        # Hash the password
        hashed_password = generate_password_hash(password)
        
        # Create new user
        try:
            cur.execute("""
                INSERT INTO users (username, password_hash, full_name, email, role)
                VALUES (%s, %s, %s, %s, %s)
            """, (username, hashed_password, full_name, email, role))
            mysql.connection.commit()
            cur.close()
            
            # Auto-login after registration
            session['user_id'] = cur.lastrowid
            session['username'] = username
            session['role'] = role
            
            return redirect(url_for('dashboard'))
        except Exception as e:
            mysql.connection.rollback()
            cur.close()
            return render_template('register.html', error='An error occurred during registration')
    
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        cur = get_db_connection()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Invalid username or password')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Get project statistics
    cur = get_db_connection()
    
    # Project counts by status
    cur.execute("""
        SELECT status, COUNT(*) as count 
        FROM projects 
        GROUP BY status
    """)
    project_status = cur.fetchall()
    
    # Task counts by status
    cur.execute("""
        SELECT status, COUNT(*) as count 
        FROM tasks 
        GROUP BY status
    """)
    task_status = cur.fetchall()
    
    # Recent projects
    cur.execute("""
        SELECT project_id, project_name, start_date, end_date, status 
        FROM projects 
        ORDER BY created_at DESC 
        LIMIT 5
    """)
    recent_projects = cur.fetchall()
    
    # Upcoming tasks
    cur.execute("""
        SELECT t.task_id, t.task_name, p.project_name, t.planned_start_date, t.planned_end_date 
        FROM tasks t
        JOIN projects p ON t.project_id = p.project_id
        WHERE t.status IN ('not_started', 'in_progress')
        ORDER BY t.planned_start_date ASC
        LIMIT 5
    """)
    upcoming_tasks = cur.fetchall()
    
    cur.close()
    
    return render_template('dashboard.html', 
                         project_status=project_status,
                         task_status=task_status,
                         recent_projects=recent_projects,
                         upcoming_tasks=upcoming_tasks)

@app.route('/projects')
@login_required
def projects():
    cur = get_db_connection()
    cur.execute("""
        SELECT p.*, u.username as created_by_name 
        FROM projects p
        JOIN users u ON p.created_by = u.user_id
        ORDER BY p.created_at DESC
    """)
    projects = cur.fetchall()
    cur.close()
    return render_template('projects.html', projects=projects)

@app.route('/projects/add', methods=['GET', 'POST'])
@login_required
def add_project():
    if request.method == 'POST':
        project_name = request.form['project_name']
        description = request.form['description']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        location = request.form['location']
        estimated_budget = request.form['estimated_budget']
        
        cur = get_db_connection()
        cur.execute("""
            INSERT INTO projects (project_name, description, start_date, end_date,location, estimated_budget, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (project_name, description, start_date, end_date,location, estimated_budget, session['user_id']))
        mysql.connection.commit()
        cur.close()
        
        return redirect(url_for('projects'))
    
    return render_template('add_project.html')

@app.route('/projects/<int:project_id>')
@login_required
def project_details(project_id):
    cur = get_db_connection()
    
    # Get project details
    cur.execute("""
        SELECT p.*, u.username as created_by_name 
        FROM projects p
        JOIN users u ON p.created_by = u.user_id
        WHERE p.project_id = %s
    """, (project_id,))
    project = cur.fetchone()
    
    # Get tasks for this project (only main tasks with no parent)
    cur.execute("""
        SELECT t.*, 
               (SELECT COUNT(*) FROM tasks WHERE parent_task_id = t.task_id) as subtask_count
        FROM tasks t
        WHERE t.project_id = %s AND t.parent_task_id IS NULL
        ORDER BY t.planned_start_date
    """, (project_id,))
    main_tasks = cur.fetchall()
    
    # Get all workers
    cur.execute("SELECT * FROM workers ORDER BY name")
    workers = cur.fetchall()
    
    # Get project progress - ensure we handle NULL values
    cur.execute("""
        SELECT 
            COUNT(*) as total_tasks,
            SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_tasks,
            COALESCE(SUM(estimated_cost), 0) as estimated_cost,
            COALESCE(SUM(actual_cost), 0) as actual_cost
        FROM tasks
        WHERE project_id = %s
    """, (project_id,))
    progress = cur.fetchone()
    
    # ✅ Get tasks for Gantt chart (newly added)
    cur.execute("""
        SELECT 
            task_id, 
            task_name, 
            planned_start_date as start_date,
            planned_end_date as end_date,
            status,
            (SELECT COUNT(*) FROM tasks WHERE parent_task_id = t.task_id) as has_subtasks
        FROM tasks t
        WHERE project_id = %s
        ORDER BY planned_start_date
    """, (project_id,))
    gantt_tasks = cur.fetchall()
    
    # Get materials for dropdown
    cur.execute("SELECT * FROM materials ORDER BY material_name")
    materials_list = cur.fetchall()
    
    cur.close()
    
    return render_template('project_details.html', 
                           project=project, 
                           main_tasks=main_tasks,
                           workers=workers,
                           progress=progress,
                           materials_list=materials_list,
                           gantt_tasks=gantt_tasks)  # Pass to template


@app.route('/tasks/add', methods=['POST'])
@login_required
def add_task():
    project_id = request.form['project_id']
    task_name = request.form['task_name']
    description = request.form.get('description', '')
    task_type = request.form['task_type']
    parent_task_id = request.form.get('parent_task_id', None)
    planned_start_date = request.form['planned_start_date']
    planned_end_date = request.form['planned_end_date']
    estimated_days = request.form['estimated_days']
    estimated_cost = request.form['estimated_cost']
    
    cur = get_db_connection()
    cur.execute("""
        INSERT INTO tasks (
            project_id, task_name, description, task_type, parent_task_id,
            planned_start_date, planned_end_date, estimated_days, estimated_cost
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        project_id, task_name, description, task_type, parent_task_id,
        planned_start_date, planned_end_date, estimated_days, estimated_cost
    ))
    mysql.connection.commit()
    cur.close()
    
    return redirect(url_for('project_details', project_id=project_id))

@app.route('/tasks/<int:task_id>')
@login_required
def task_details(task_id):
    cur = get_db_connection()
    
    # Get task details
    cur.execute("""
        SELECT t.*, p.project_name 
        FROM tasks t
        JOIN projects p ON t.project_id = p.project_id
        WHERE t.task_id = %s
    """, (task_id,))
    task = cur.fetchone()
    
    # Get subtasks
    cur.execute("""
        SELECT * FROM tasks 
        WHERE parent_task_id = %s
        ORDER BY planned_start_date
    """, (task_id,))
    subtasks = cur.fetchall()
    
    # Get assigned workers
    cur.execute("""
        SELECT ta.*, w.name as worker_name, w.specialization, w.daily_wage
        FROM task_assignments ta
        JOIN workers w ON ta.worker_id = w.worker_id
        WHERE ta.task_id = %s
        ORDER BY ta.assignment_date DESC
    """, (task_id,))
    assignments = cur.fetchall()
    
    # Get materials used
    cur.execute("""
        SELECT tm.*, m.material_name, m.unit, m.unit_cost
        FROM task_materials tm
        JOIN materials m ON tm.material_id = m.material_id
        WHERE tm.task_id = %s
        ORDER BY tm.date_used DESC
    """, (task_id,))
    materials = cur.fetchall()
    
    # Get all materials for dropdown
    cur.execute("SELECT * FROM materials ORDER BY material_name")
    materials_list = cur.fetchall()
    
    # Get all workers for dropdown
    cur.execute("SELECT * FROM workers ORDER BY name")
    workers = cur.fetchall()
    
    # Get daily progress
    cur.execute("""
        SELECT dp.*, u.username as created_by_name
        FROM daily_progress dp
        JOIN users u ON dp.created_by = u.user_id
        WHERE dp.task_id = %s
        ORDER BY dp.progress_date DESC
    """, (task_id,))
    progress = cur.fetchall()
    
    # Calculate total costs
    labor_cost = sum(a['hours_worked'] * (a['daily_wage'] / 8) for a in assignments) if assignments else 0
    material_cost = sum(m['total_cost'] or 0 for m in materials) if materials else 0
    total_cost = labor_cost + material_cost
    
    cur.close()
    
    return render_template('task_details.html', 
                         task=task,
                         subtasks=subtasks,
                         assignments=assignments,
                         materials=materials,
                         materials_list=materials_list,
                         workers=workers,
                         progress=progress,
                         labor_cost=labor_cost,
                         material_cost=material_cost,
                         total_cost=total_cost)
@app.route('/assign_worker', methods=['POST'])
@login_required
def assign_worker():
    task_id = request.form['task_id']
    worker_id = request.form['worker_id']
    assignment_date = request.form['assignment_date']
    hours_worked = request.form['hours_worked']
    notes = request.form.get('notes', '')
    
    cur = get_db_connection()
    cur.execute("""
        INSERT INTO task_assignments (task_id, worker_id, assignment_date, hours_worked, notes)
        VALUES (%s, %s, %s, %s, %s)
    """, (task_id, worker_id, assignment_date, hours_worked, notes))
    mysql.connection.commit()
    
    # Update task status to in_progress if not already
    cur.execute("""
        UPDATE tasks 
        SET status = 'in_progress' 
        WHERE task_id = %s AND status = 'not_started'
    """, (task_id,))
    mysql.connection.commit()
    
    cur.close()
    
    return redirect(url_for('task_details', task_id=task_id))

@app.route('/add_material', methods=['POST'])
@login_required
def add_material():
    task_id = request.form['task_id']
    material_id = request.form['material_id']
    quantity = request.form['quantity']
    date_used = request.form['date_used']
    notes = request.form.get('notes', '')
    
    cur = get_db_connection()
    cur.execute("""
        INSERT INTO task_materials (task_id, material_id, quantity, date_used, notes)
        VALUES (%s, %s, %s, %s, %s)
    """, (task_id, material_id, quantity, date_used, notes))
    mysql.connection.commit()
    
    # Update task actual cost
    cur.execute("""
        UPDATE tasks t
        SET t.actual_cost = (
            SELECT IFNULL(SUM(tm.total_cost), 0)
            FROM task_materials tm
            WHERE tm.task_id = %s
        ) + (
            SELECT IFNULL(SUM(ta.hours_worked * (w.daily_wage / 8)), 0)
            FROM task_assignments ta
            JOIN workers w ON ta.worker_id = w.worker_id
            WHERE ta.task_id = %s
        )
        WHERE t.task_id = %s
    """, (task_id, task_id, task_id))
    mysql.connection.commit()
    
    cur.close()
    
    return redirect(url_for('task_details', task_id=task_id))

@app.route('/record_progress', methods=['POST'])
@login_required
def record_progress():
    task_id = request.form['task_id']
    progress_date = request.form['progress_date']
    percentage_completed = request.form['percentage_completed']
    notes = request.form.get('notes', '')
    
    cur = get_db_connection()
    cur.execute("""
        INSERT INTO daily_progress (task_id, progress_date, percentage_completed, notes, created_by)
        VALUES (%s, %s, %s, %s, %s)
    """, (task_id, progress_date, percentage_completed, notes, session['user_id']))
    mysql.connection.commit()
    
    # Update task status if completed
    if float(percentage_completed) >= 100:
        cur.execute("""
            UPDATE tasks 
            SET status = 'completed', actual_end_date = %s 
            WHERE task_id = %s
        """, (progress_date, task_id))
        mysql.connection.commit()
    
    cur.close()
    
    return redirect(url_for('task_details', task_id=task_id))

@app.route('/workers')
@login_required
def workers():
    cur = get_db_connection()
    cur.execute("SELECT * FROM workers ORDER BY name")
    workers = cur.fetchall()
    cur.close()
    return render_template('workers.html', workers=workers)

# Update Project Route
@app.route('/projects/<int:project_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    cur = get_db_connection()
    
    if request.method == 'POST':
        project_name = request.form['project_name']
        description = request.form['description']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        estimated_budget = request.form['estimated_budget']
        status = request.form['status']
        
        cur.execute("""
            UPDATE projects 
            SET project_name = %s, description = %s, start_date = %s, 
                end_date = %s, estimated_budget = %s, status = %s
            WHERE project_id = %s
        """, (project_name, description, start_date, end_date, estimated_budget, status, project_id))
        mysql.connection.commit()
        cur.close()
        
        return redirect(url_for('project_details', project_id=project_id))
    
    # GET request - show edit form
    cur.execute("SELECT * FROM projects WHERE project_id = %s", (project_id,))
    project = cur.fetchone()
    cur.close()
    
    return render_template('edit_project.html', project=project)

# Update Task Route
@app.route('/tasks/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_task(task_id):
    cur = get_db_connection()
    
    if request.method == 'POST':
        task_name = request.form['task_name']
        description = request.form['description']
        task_type = request.form['task_type']
        planned_start_date = request.form['planned_start_date']
        planned_end_date = request.form['planned_end_date']
        estimated_days = request.form['estimated_days']
        estimated_cost = request.form['estimated_cost']
        status = request.form['status']
        
        cur.execute("""
            UPDATE tasks 
            SET task_name = %s, description = %s, task_type = %s,
                planned_start_date = %s, planned_end_date = %s,
                estimated_days = %s, estimated_cost = %s, status = %s
            WHERE task_id = %s
        """, (task_name, description, task_type, planned_start_date, 
              planned_end_date, estimated_days, estimated_cost, status, task_id))
        mysql.connection.commit()
        cur.close()
        
        return redirect(url_for('task_details', task_id=task_id))
    
    # GET request - show edit form
    cur.execute("SELECT * FROM tasks WHERE task_id = %s", (task_id,))
    task = cur.fetchone()
    cur.close()
    
    return render_template('edit_task.html', task=task)

# Update Material Route
@app.route('/materials/<int:material_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_material(material_id):
    cur = get_db_connection()
    
    if request.method == 'POST':
        material_name = request.form['material_name']
        unit = request.form['unit']
        unit_cost = request.form['unit_cost']
        description = request.form['description']
        
        cur.execute("""
            UPDATE materials 
            SET material_name = %s, unit = %s, unit_cost = %s, description = %s
            WHERE material_id = %s
        """, (material_name, unit, unit_cost, description, material_id))
        mysql.connection.commit()
        cur.close()
        
        return redirect(url_for('materials'))
    
    # GET request - show edit form
    cur.execute("SELECT * FROM materials WHERE material_id = %s", (material_id,))
    material = cur.fetchone()
    cur.close()
    
    return render_template('edit_material.html', material=material)

@app.route('/workers/add', methods=['GET', 'POST'])
@login_required
def add_worker():
    if request.method == 'POST':
        name = request.form['name']
        contact_number = request.form['contact_number']
        email = request.form['email']
        specialization = request.form['specialization']
        daily_wage = request.form['daily_wage']
        
        cur = get_db_connection()
        cur.execute("""
            INSERT INTO workers (name, contact_number, email, specialization, daily_wage)
            VALUES (%s, %s, %s, %s, %s)
        """, (name, contact_number, email, specialization, daily_wage))
        mysql.connection.commit()
        cur.close()
        
        return redirect(url_for('workers'))
    
    return render_template('add_worker.html')

@app.route('/materials')
@login_required
def materials():
    cur = get_db_connection()
    cur.execute("SELECT * FROM materials ORDER BY material_name")
    materials = cur.fetchall()
    cur.close()
    return render_template('materials.html', materials=materials)

@app.route('/materials/add', methods=['GET', 'POST'])
@login_required
def add_material_item():
    if request.method == 'POST':
        material_name = request.form['material_name']
        unit = request.form['unit']
        unit_cost = request.form['unit_cost']
        description = request.form.get('description', '')
        
        cur = get_db_connection()
        cur.execute("""
            INSERT INTO materials (material_name, unit, unit_cost, description)
            VALUES (%s, %s, %s, %s)
        """, (material_name, unit, unit_cost, description))
        mysql.connection.commit()
        cur.close()
        
        return redirect(url_for('materials'))
    
    return render_template('add_material.html')

@app.route('/reports')
def reports():
    return render_template('reports.html')

from datetime import datetime
import json
from flask import render_template, redirect, url_for, flash
from flask_login import login_required

@app.route('/reports/project/<int:project_id>')
def project_report(project_id):
    cur = get_db_connection()
    
    # Get project details
    cur.execute("SELECT * FROM projects WHERE project_id = %s", (project_id,))
    project = cur.fetchone()
    
    # Get all tasks with their costs
    cur.execute("""
        SELECT t.*, 
               (SELECT IFNULL(SUM(tm.total_cost), 0)
               FROM task_materials tm
               WHERE tm.task_id = t.task_id) as material_cost,
               (SELECT IFNULL(SUM(ta.hours_worked * (w.daily_wage / 8)), 0)
               FROM task_assignments ta
               JOIN workers w ON ta.worker_id = w.worker_id
               WHERE ta.task_id = t.task_id) as labor_cost
        FROM tasks t
        WHERE t.project_id = %s
        ORDER BY t.planned_start_date
    """, (project_id,))
    tasks = cur.fetchall()
    
    # Calculate totals
    total_estimated = sum(t['estimated_cost'] for t in tasks)
    total_material = sum(t['material_cost'] for t in tasks)
    total_labor = sum(t['labor_cost'] for t in tasks)
    total_actual = total_material + total_labor
    
    # Get progress data for charts
    cur.execute("""
        SELECT progress_date, AVG(percentage_completed) as avg_progress
        FROM daily_progress
        WHERE task_id IN (SELECT task_id FROM tasks WHERE project_id = %s)
        GROUP BY progress_date
        ORDER BY progress_date
    """, (project_id,))
    progress_data = cur.fetchall()
    
    cur.close()

    # Prepare data for charts
    progress_dates = [str(p['progress_date']) for p in progress_data]
    progress_values = [float(p['avg_progress']) for p in progress_data]
    
    cost_data = {
        'labels': ['Materials', 'Labor'],
        'values': [float(total_material), float(total_labor)]
    }

    # ✅ Budget Forecast Calculation
    today = date.today()

    # Ensure start and end dates are datetime.date objects
    project_start = project['start_date'] if isinstance(project['start_date'], date) else datetime.strptime(project['start_date'], '%Y-%m-%d').date()
    project_end = project['end_date'] if isinstance(project['end_date'], date) else datetime.strptime(project['end_date'], '%Y-%m-%d').date()

    total_days = (project_end - project_start).days
    days_passed = (today - project_start).days if today > project_start else 0
    completion_percentage = (days_passed / total_days) * 100 if total_days > 0 else 0

    budget_forecast = {
    'total_days': total_days,
    'days_passed': days_passed,
    'completion_percentage': round(completion_percentage, 2),
    'budget_utilization': round(float(total_actual) / float(project['estimated_budget']) * 100, 2) if project['estimated_budget'] > 0 else 0,
    'forecast_completion': round(float(project['estimated_budget']) * (completion_percentage / 100), 2) if completion_percentage > 0 else 0,
    'variance': round(float(total_actual) - (float(project['estimated_budget']) * (completion_percentage / 100)), 2) if completion_percentage > 0 else 0
}

    return render_template('project_report.html',
                       project=project,
                       tasks=tasks,
                       total_estimated=total_estimated,
                       total_actual=total_actual,
                       progress_dates=json.dumps(progress_dates),
                       progress_values=json.dumps(progress_values),
                       cost_data=json.dumps(cost_data),
                       budget_forecast=budget_forecast,
                       abs=abs)  # <--- Add this line

@app.route('/export/project/<int:project_id>')
# @login_required
def export_project(project_id):
    cur = get_db_connection()
    
    try:
        # Get project details
        cur.execute("SELECT * FROM projects WHERE project_id = %s", (project_id,))
        project = cur.fetchone()
        
        if not project:
            flash("Project not found", "danger")
            return redirect(url_for('projects'))

        # Get all tasks with their costs
        cur.execute("""
            SELECT 
                t.task_id, 
                t.task_name, 
                t.task_type, 
                t.planned_start_date, 
                t.planned_end_date,
                t.estimated_days, 
                t.estimated_cost,
                t.status, 
                t.actual_start_date, 
                t.actual_end_date,
                COALESCE((
                    SELECT SUM(tm.total_cost)
                    FROM task_materials tm
                    WHERE tm.task_id = t.task_id
                ), 0) as material_cost,
                COALESCE((
                    SELECT SUM(ta.hours_worked * (w.daily_wage / 8))
                    FROM task_assignments ta
                    JOIN workers w ON ta.worker_id = w.worker_id
                    WHERE ta.task_id = t.task_id
                ), 0) as labor_cost,
                COALESCE((
                    SELECT SUM(tm.total_cost)
                    FROM task_materials tm
                    WHERE tm.task_id = t.task_id
                ), 0) + COALESCE((
                    SELECT SUM(ta.hours_worked * (w.daily_wage / 8))
                    FROM task_assignments ta
                    JOIN workers w ON ta.worker_id = w.worker_id
                    WHERE ta.task_id = t.task_id
                ), 0) as total_cost,
                t.parent_task_id,
                (SELECT task_name FROM tasks WHERE task_id = t.parent_task_id) as parent_task_name
            FROM tasks t
            WHERE t.project_id = %s
            ORDER BY t.planned_start_date
        """, (project_id,))
        tasks = cur.fetchall()
        
        # Get workers assigned
        cur.execute("""
            SELECT 
                ta.task_id, 
                t.task_name, 
                w.name as worker_name, 
                w.specialization,
                w.daily_wage,
                ta.assignment_date, 
                ta.hours_worked,
                (ta.hours_worked * (w.daily_wage / 8)) as cost
            FROM task_assignments ta
            JOIN workers w ON ta.worker_id = w.worker_id
            JOIN tasks t ON ta.task_id = t.task_id
            WHERE t.project_id = %s
            ORDER BY ta.assignment_date
        """, (project_id,))
        workers = cur.fetchall()
        
        # Get materials used
        cur.execute("""
            SELECT 
                tm.task_id, 
                t.task_name, 
                m.material_name, 
                tm.quantity, 
                m.unit, 
                m.unit_cost,
                tm.total_cost, 
                tm.date_used
            FROM task_materials tm
            JOIN materials m ON tm.material_id = m.material_id
            JOIN tasks t ON tm.task_id = t.task_id
            WHERE t.project_id = %s
            ORDER BY tm.date_used
        """, (project_id,))
        materials = cur.fetchall()
        
        # Create Excel file
        with pd.ExcelWriter('project_report.xlsx') as writer:
            # Project summary sheet
            summary_data = {
                'Project Name': [project['project_name']],
                'Start Date': [project['start_date']],
                'End Date': [project['end_date']],
                'Status': [project['status'].replace('_', ' ').title()],
                'Estimated Budget': [project['estimated_budget']],
                'Total Estimated Cost': [sum(t['estimated_cost'] for t in tasks)],
                'Total Actual Cost': [sum(t['total_cost'] for t in tasks)],
                'Budget Variance': [sum(t['total_cost'] for t in tasks) - project['estimated_budget']]
            }
            pd.DataFrame(summary_data).to_excel(writer, sheet_name='Project Summary', index=False)
            
            # Tasks sheet
            tasks_data = []
            for task in tasks:
                tasks_data.append({
                    'Task ID': task['task_id'],
                    'Task Name': task['task_name'],
                    'Parent Task': task['parent_task_name'] or 'Main Task',
                    'Type': task['task_type'].title(),
                    'Status': task['status'].replace('_', ' ').title(),
                    'Planned Start': task['planned_start_date'],
                    'Planned End': task['planned_end_date'],
                    'Actual Start': task['actual_start_date'] or 'Not started',
                    'Actual End': task['actual_end_date'] or 'In progress',
                    'Estimated Days': task['estimated_days'],
                    'Estimated Cost': task['estimated_cost'],
                    'Material Cost': task['material_cost'],
                    'Labor Cost': task['labor_cost'],
                    'Total Cost': task['total_cost'],
                    'Cost Variance': task['total_cost'] - task['estimated_cost']
                })
            tasks_df = pd.DataFrame(tasks_data)
            tasks_df.to_excel(writer, sheet_name='Tasks', index=False)
            
            # Workers sheet
            workers_data = []
            for worker in workers:
                workers_data.append({
                    'Task ID': worker['task_id'],
                    'Task Name': worker['task_name'],
                    'Worker Name': worker['worker_name'],
                    'Specialization': worker['specialization'],
                    'Daily Wage': worker['daily_wage'],
                    'Assignment Date': worker['assignment_date'],
                    'Hours Worked': worker['hours_worked'],
                    'Cost': worker['cost']
                })
            workers_df = pd.DataFrame(workers_data)
            workers_df.to_excel(writer, sheet_name='Workers', index=False)
            
            # Materials sheet
            materials_data = []
            for material in materials:
                materials_data.append({
                    'Task ID': material['task_id'],
                    'Task Name': material['task_name'],
                    'Material Name': material['material_name'],
                    'Quantity': material['quantity'],
                    'Unit': material['unit'],
                    'Unit Cost': material['unit_cost'],
                    'Total Cost': material['total_cost'],
                    'Date Used': material['date_used']
                })
            materials_df = pd.DataFrame(materials_data)
            materials_df.to_excel(writer, sheet_name='Materials', index=False)
            
            # Cost Summary sheet
            cost_summary = {
                'Cost Type': ['Materials', 'Labor', 'Total'],
                'Amount': [
                    sum(t['material_cost'] for t in tasks),
                    sum(t['labor_cost'] for t in tasks),
                    sum(t['total_cost'] for t in tasks)
                ]
            }
            pd.DataFrame(cost_summary).to_excel(writer, sheet_name='Cost Summary', index=False)
        
        cur.close()
        return send_file('project_report.xlsx', as_attachment=True, download_name=f"{project['project_name']}_report.xlsx")
        
    except Exception as e:
        if cur:
            cur.close()
        flash(f"Error generating report: {str(e)}", "danger")
        return redirect(url_for('project_details', project_id=project_id))
    
# Configuration
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx', 'xls', 'xlsx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Add after materials routes
@app.route('/documents')
# @login_required
def documents():
    cur = get_db_connection()
    cur.execute("""
        SELECT d.*, p.project_name, u.username as uploaded_by 
        FROM documents d
        LEFT JOIN projects p ON d.project_id = p.project_id
        JOIN users u ON d.uploaded_by = u.user_id
        ORDER BY d.upload_date DESC
    """)
    documents = cur.fetchall()
    cur.execute("SELECT project_id, project_name FROM projects")
    projects = cur.fetchall()
    cur.close()
    return render_template('documents.html', documents=documents, projects=projects)

@app.route('/documents/upload', methods=['POST'])
# @login_required
def upload_document():
    if 'file' not in request.files:
        flash('No file selected', 'danger')
        return redirect(url_for('documents'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'danger')
        return redirect(url_for('documents'))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
        
        project_id = request.form.get('project_id')
        document_name = request.form.get('document_name')
        description = request.form.get('description', '')
        
        cur = get_db_connection()
        cur.execute("""
            INSERT INTO documents (document_name, file_path, description, project_id, uploaded_by)
            VALUES (%s, %s, %s, %s, %s)
        """, (document_name, unique_filename, description, project_id, session['user_id']))
        mysql.connection.commit()
        cur.close()
        
        flash('Document uploaded successfully', 'success')
    else:
        flash('Invalid file type', 'danger')
    
    return redirect(url_for('documents'))

@app.route('/documents/download/<int:document_id>')
# @login_required
def download_document(document_id):
    cur = get_db_connection()
    cur.execute("SELECT file_path, document_name FROM documents WHERE document_id = %s", (document_id,))
    document = cur.fetchone()
    cur.close()
    
    if document:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], document['file_path'])
        try:
            # Get the file extension
            file_ext = os.path.splitext(document['file_path'])[1].lower()
            # Set appropriate download name with original extension
            download_name = f"{secure_filename(document['document_name'])}{file_ext}"
            return send_file(file_path, as_attachment=True, download_name=download_name)
        except FileNotFoundError:
            flash('File not found on server', 'danger')
    else:
        flash('Document not found', 'danger')
    return redirect(url_for('documents'))

@app.route('/documents/delete/<int:document_id>', methods=['POST'])
# @login_required
def delete_document(document_id):
    cur = get_db_connection()
    cur.execute("SELECT file_path FROM documents WHERE document_id = %s", (document_id,))
    document = cur.fetchone()
    
    if document:
        try:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], document['file_path'])
            if os.path.exists(file_path):
                os.remove(file_path)
            
            cur.execute("DELETE FROM documents WHERE document_id = %s", (document_id,))
            mysql.connection.commit()
            flash('Document deleted successfully', 'success')
        except Exception as e:
            mysql.connection.rollback()
            flash(f'Error deleting document: {str(e)}', 'danger')
    else:
        flash('Document not found', 'danger')
    
    cur.close()
    return redirect(url_for('documents'))

# Add after documents routes
@app.route('/equipment')
# @login_required
def equipment():
    cur = get_db_connection()
    cur.execute("""
        SELECT e.*, p.project_name 
        FROM equipment e
        LEFT JOIN projects p ON e.assigned_project = p.project_id
        ORDER BY e.equipment_name
    """)
    equipment_list = cur.fetchall()
    cur.execute("SELECT project_id, project_name FROM projects")
    projects = cur.fetchall()
    cur.close()
    return render_template('equipment.html', equipment=equipment_list, projects=projects)

@app.route('/equipment/add', methods=['POST'])
# @login_required
def add_equipment():
    equipment_name = request.form['equipment_name']
    equipment_type = request.form['equipment_type']
    serial_number = request.form.get('serial_number', '')
    purchase_date = request.form.get('purchase_date')
    purchase_cost = request.form.get('purchase_cost', 0)
    assigned_project = request.form.get('assigned_project')
    status = request.form['status']
    notes = request.form.get('notes', '')
    
    cur = get_db_connection()
    cur.execute("""
        INSERT INTO equipment (
            equipment_name, equipment_type, serial_number, 
            purchase_date, purchase_cost, assigned_project, 
            status, notes
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        equipment_name, equipment_type, serial_number,
        purchase_date, purchase_cost, assigned_project,
        status, notes
    ))
    mysql.connection.commit()
    cur.close()
    
    flash('Equipment added successfully', 'success')
    return redirect(url_for('equipment'))

@app.route('/equipment/<int:equipment_id>/update', methods=['POST'])
# @login_required
def update_equipment(equipment_id):
    equipment_name = request.form['equipment_name']
    equipment_type = request.form['equipment_type']
    serial_number = request.form.get('serial_number', '')
    purchase_date = request.form.get('purchase_date')
    purchase_cost = request.form.get('purchase_cost', 0)
    assigned_project = request.form.get('assigned_project')
    status = request.form['status']
    notes = request.form.get('notes', '')
    
    cur = get_db_connection()
    cur.execute("""
        UPDATE equipment SET
            equipment_name = %s,
            equipment_type = %s,
            serial_number = %s,
            purchase_date = %s,
            purchase_cost = %s,
            assigned_project = %s,
            status = %s,
            notes = %s
        WHERE equipment_id = %s
    """, (
        equipment_name, equipment_type, serial_number,
        purchase_date, purchase_cost, assigned_project,
        status, notes, equipment_id
    ))
    mysql.connection.commit()
    cur.close()
    
    flash('Equipment updated successfully', 'success')
    return redirect(url_for('equipment'))

@app.route('/equipment/<int:equipment_id>/delete', methods=['POST'])
# @login_required
def delete_equipment(equipment_id):
    cur = get_db_connection()
    cur.execute("DELETE FROM equipment WHERE equipment_id = %s", (equipment_id,))
    mysql.connection.commit()
    cur.close()
    
    flash('Equipment deleted successfully', 'success')
    return redirect(url_for('equipment'))

# Add after equipment routes
@app.route('/safety')
# @login_required
def safety():
    cur = get_db_connection()
    cur.execute("""
        SELECT s.*, p.project_name, u.username as reported_by 
        FROM safety_incidents s
        LEFT JOIN projects p ON s.project_id = p.project_id
        JOIN users u ON s.reported_by = u.user_id
        ORDER BY s.incident_date DESC
    """)
    incidents = cur.fetchall()
    cur.execute("SELECT project_id, project_name FROM projects")
    projects = cur.fetchall()
    cur.close()
    return render_template('safety.html', incidents=incidents, projects=projects)

@app.route('/safety/add', methods=['POST'])
# @login_required
def add_safety_incident():
    incident_type = request.form['incident_type']
    incident_date = request.form['incident_date']
    project_id = request.form.get('project_id')
    location = request.form['location']
    description = request.form['description']
    severity = request.form['severity']
    action_taken = request.form['action_taken']
    reported_by = session['user_id']
    
    cur = get_db_connection()
    cur.execute("""
        INSERT INTO safety_incidents (
            incident_type, incident_date, project_id, 
            location, description, severity, 
            action_taken, reported_by
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        incident_type, incident_date, project_id,
        location, description, severity,
        action_taken, reported_by
    ))
    mysql.connection.commit()
    cur.close()
    
    flash('Safety incident recorded successfully', 'success')
    return redirect(url_for('safety'))

@app.route('/safety/<int:incident_id>/update', methods=['POST'])
# @login_required
def update_safety_incident(incident_id):
    incident_type = request.form['incident_type']
    incident_date = request.form['incident_date']
    project_id = request.form.get('project_id')
    location = request.form['location']
    description = request.form['description']
    severity = request.form['severity']
    action_taken = request.form['action_taken']
    
    cur = get_db_connection()
    cur.execute("""
        UPDATE safety_incidents SET
            incident_type = %s,
            incident_date = %s,
            project_id = %s,
            location = %s,
            description = %s,
            severity = %s,
            action_taken = %s
        WHERE incident_id = %s
    """, (
        incident_type, incident_date, project_id,
        location, description, severity,
        action_taken, incident_id
    ))
    mysql.connection.commit()
    cur.close()
    
    flash('Safety incident updated successfully', 'success')
    return redirect(url_for('safety'))

@app.route('/safety/<int:incident_id>/delete', methods=['POST'])
# @login_required
def delete_safety_incident(incident_id):
    cur = get_db_connection()
    cur.execute("DELETE FROM safety_incidents WHERE incident_id = %s", (incident_id,))
    mysql.connection.commit()
    cur.close()
    
    flash('Safety incident deleted successfully', 'success')
    return redirect(url_for('safety'))

@app.route('/weather/<int:project_id>')
def weather_forecast(project_id):
    cur = get_db_connection()
    cur.execute("SELECT project_id, project_name, location FROM projects WHERE project_id = %s", (project_id,))
    project = cur.fetchone()
    cur.close()

    if not project or not project['location']:
        flash('Project location not set', 'warning')
        return redirect(url_for('project_details', project_id=project_id))

    location = project['location']

    try:
        geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={location}&limit=1&appid={WEATHER_API_KEY}"
        geo_response = requests.get(geo_url)
        geo_data = geo_response.json()

        if not geo_data:
            flash('Location not found in weather service', 'danger')
            return redirect(url_for('project_details', project_id=project_id))

        lat = geo_data[0]['lat']
        lon = geo_data[0]['lon']

        weather_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={WEATHER_API_KEY}&units=metric"
        weather_response = requests.get(weather_url)
        weather_data = weather_response.json()

        if 'list' not in weather_data:
            flash('Weather forecast not available', 'danger')
            return redirect(url_for('project_details', project_id=project_id))

        forecast = []
        temp_chart = []
        rain_chart = []

        for item in weather_data['list']:
            dt_txt = item.get('dt_txt')
            timestamp = datetime.strptime(dt_txt, '%Y-%m-%d %H:%M:%S')
            time_str = timestamp.strftime('%Y-%m-%d %H:%M')

            temp = item['main']['temp']
            rain = item.get('rain', {}).get('3h', 0)

            forecast.append({
                'datetime': time_str,
                'temp': temp,
                'feels_like': item['main']['feels_like'],
                'humidity': item['main']['humidity'],
                'pressure': item['main']['pressure'],
                'description': item['weather'][0]['description'],
                'icon': item['weather'][0]['icon'],
                'wind_speed': item['wind']['speed'],
                'rain': rain,
                'snow': item.get('snow', {}).get('3h', 0)
            })

            if timestamp.hour == 12:
                temp_chart.append({'date': timestamp.strftime('%d-%b'), 'temp': temp})
                rain_chart.append({'date': timestamp.strftime('%d-%b'), 'rain': rain})

        return render_template('weather.html',
                               project=project,
                               forecast=forecast,
                               location=location,
                               temp_chart=temp_chart,
                               rain_chart=rain_chart)

    except Exception as e:
        flash(f'Error fetching weather data: {str(e)}', 'danger')
        return redirect(url_for('project_details', project_id=project_id))



# Add after safety routes
@app.route('/subcontractors')
# @login_required
def subcontractors():
    cur = get_db_connection()
    cur.execute("""
        SELECT s.*, GROUP_CONCAT(p.project_name SEPARATOR ', ') as projects
        FROM subcontractors s
        LEFT JOIN subcontractor_projects sp ON s.subcontractor_id = sp.subcontractor_id
        LEFT JOIN projects p ON sp.project_id = p.project_id
        GROUP BY s.subcontractor_id
        ORDER BY s.company_name
    """)
    subcontractors = cur.fetchall()
    cur.execute("SELECT project_id, project_name FROM projects")
    projects = cur.fetchall()
    cur.close()
    return render_template('subcontractors.html', subcontractors=subcontractors, projects=projects)

@app.route('/subcontractors/add', methods=['POST'])
# @login_required
def add_subcontractor():
    company_name = request.form['company_name']
    contact_person = request.form['contact_person']
    email = request.form['email']
    phone = request.form['phone']
    specialty = request.form['specialty']
    contract_details = request.form.get('contract_details', '')
    selected_projects = request.form.getlist('projects')
    
    cur = get_db_connection()
    try:
        cur.execute("""
            INSERT INTO subcontractors (
                company_name, contact_person, email, 
                phone, specialty, contract_details
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """, (company_name, contact_person, email, phone, specialty, contract_details))
        subcontractor_id = cur.lastrowid
        
        for project_id in selected_projects:
            cur.execute("""
                INSERT INTO subcontractor_projects (subcontractor_id, project_id)
                VALUES (%s, %s)
            """, (subcontractor_id, project_id))
        
        mysql.connection.commit()
        flash('Subcontractor added successfully', 'success')
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error adding subcontractor: {str(e)}', 'danger')
    finally:
        cur.close()
    
    return redirect(url_for('subcontractors'))

@app.route('/subcontractors/<int:subcontractor_id>/update', methods=['POST'])
# @login_required
def update_subcontractor(subcontractor_id):
    company_name = request.form['company_name']
    contact_person = request.form['contact_person']
    email = request.form['email']
    phone = request.form['phone']
    specialty = request.form['specialty']
    contract_details = request.form.get('contract_details', '')
    selected_projects = request.form.getlist('projects')
    
    cur = get_db_connection()
    try:
        cur.execute("""
            UPDATE subcontractors SET
                company_name = %s,
                contact_person = %s,
                email = %s,
                phone = %s,
                specialty = %s,
                contract_details = %s
            WHERE subcontractor_id = %s
        """, (company_name, contact_person, email, phone, specialty, contract_details, subcontractor_id))
        
        # Update projects
        cur.execute("DELETE FROM subcontractor_projects WHERE subcontractor_id = %s", (subcontractor_id,))
        for project_id in selected_projects:
            cur.execute("""
                INSERT INTO subcontractor_projects (subcontractor_id, project_id)
                VALUES (%s, %s)
            """, (subcontractor_id, project_id))
        
        mysql.connection.commit()
        flash('Subcontractor updated successfully', 'success')
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error updating subcontractor: {str(e)}', 'danger')
    finally:
        cur.close()
    
    return redirect(url_for('subcontractors'))

@app.route('/subcontractors/<int:subcontractor_id>/delete', methods=['POST'])
# @login_required
def delete_subcontractor(subcontractor_id):
    cur = get_db_connection()
    try:
        cur.execute("DELETE FROM subcontractor_projects WHERE subcontractor_id = %s", (subcontractor_id,))
        cur.execute("DELETE FROM subcontractors WHERE subcontractor_id = %s", (subcontractor_id,))
        mysql.connection.commit()
        flash('Subcontractor deleted successfully', 'success')
    except Exception as e:
        mysql.connection.rollback()
        flash(f'Error deleting subcontractor: {str(e)}', 'danger')
    finally:
        cur.close()
    
    return redirect(url_for('subcontractors'))

if __name__ == '__main__':
    app.run(debug=True)