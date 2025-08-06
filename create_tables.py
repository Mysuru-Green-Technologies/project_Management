import mysql.connector
from mysql.connector import Error

# Your SQL schema
sql_script = """
CREATE DATABASE IF NOT EXISTS construction_project_management;
USE construction_project_management;

CREATE TABLE IF NOT EXISTS users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    role ENUM('admin', 'manager', 'supervisor', 'worker') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projects (
    project_id INT AUTO_INCREMENT PRIMARY KEY,
    project_name VARCHAR(100) NOT NULL,
    description TEXT,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    estimated_budget DECIMAL(15,2),
    actual_budget DECIMAL(15,2) DEFAULT 0,
    status ENUM('planned', 'in_progress', 'on_hold', 'completed', 'cancelled') DEFAULT 'planned',
    created_by INT NOT NULL,
    location VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id INT AUTO_INCREMENT PRIMARY KEY,
    project_id INT NOT NULL,
    task_name VARCHAR(100) NOT NULL,
    description TEXT,
    task_type ENUM('yearly', 'monthly', 'weekly', 'daily') NOT NULL,
    parent_task_id INT NULL,
    planned_start_date DATE NOT NULL,
    planned_end_date DATE NOT NULL,
    actual_start_date DATE,
    actual_end_date DATE,
    estimated_days INT NOT NULL,
    estimated_cost DECIMAL(15,2) NOT NULL,
    actual_cost DECIMAL(15,2) DEFAULT 0,
    status ENUM('not_started', 'in_progress', 'completed', 'delayed') DEFAULT 'not_started',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(project_id),
    FOREIGN KEY (parent_task_id) REFERENCES tasks(task_id)
);

CREATE TABLE IF NOT EXISTS workers (
    worker_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    contact_number VARCHAR(20),
    email VARCHAR(100),
    specialization VARCHAR(100),
    daily_wage DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_assignments (
    assignment_id INT AUTO_INCREMENT PRIMARY KEY,
    task_id INT NOT NULL,
    worker_id INT NOT NULL,
    assignment_date DATE NOT NULL,
    hours_worked DECIMAL(5,2) NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id),
    FOREIGN KEY (worker_id) REFERENCES workers(worker_id)
);

CREATE TABLE IF NOT EXISTS materials (
    material_id INT AUTO_INCREMENT PRIMARY KEY,
    material_name VARCHAR(100) NOT NULL,
    unit VARCHAR(20) NOT NULL,
    unit_cost DECIMAL(10,2) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_materials (
    task_material_id INT AUTO_INCREMENT PRIMARY KEY,
    task_id INT NOT NULL,
    material_id INT NOT NULL,
    quantity DECIMAL(10,2) NOT NULL,
    total_cost DECIMAL(15,2),
    date_used DATE NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id),
    FOREIGN KEY (material_id) REFERENCES materials(material_id)
);

CREATE TABLE IF NOT EXISTS daily_progress (
    progress_id INT AUTO_INCREMENT PRIMARY KEY,
    task_id INT NOT NULL,
    progress_date DATE NOT NULL,
    percentage_completed DECIMAL(5,2) NOT NULL,
    notes TEXT,
    created_by INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id),
    FOREIGN KEY (created_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS documents (
    document_id INT AUTO_INCREMENT PRIMARY KEY,
    document_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(255) NOT NULL,
    description TEXT,
    project_id INT,
    uploaded_by INT NOT NULL,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(project_id),
    FOREIGN KEY (uploaded_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS equipment (
    equipment_id INT AUTO_INCREMENT PRIMARY KEY,
    equipment_name VARCHAR(100) NOT NULL,
    equipment_type VARCHAR(50) NOT NULL,
    serial_number VARCHAR(100),
    purchase_date DATE,
    purchase_cost DECIMAL(15,2),
    assigned_project INT,
    status ENUM('available', 'in_use', 'maintenance', 'retired') DEFAULT 'available',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (assigned_project) REFERENCES projects(project_id)
);

CREATE TABLE IF NOT EXISTS safety_incidents (
    incident_id INT AUTO_INCREMENT PRIMARY KEY,
    incident_type VARCHAR(100) NOT NULL,
    incident_date DATE NOT NULL,
    project_id INT,
    location VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    severity ENUM('low', 'medium', 'high', 'critical') NOT NULL,
    action_taken TEXT NOT NULL,
    reported_by INT NOT NULL,
    reported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(project_id),
    FOREIGN KEY (reported_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS subcontractors (
    subcontractor_id INT AUTO_INCREMENT PRIMARY KEY,
    company_name VARCHAR(100) NOT NULL,
    contact_person VARCHAR(100) NOT NULL,
    email VARCHAR(100),
    phone VARCHAR(20),
    specialty VARCHAR(100) NOT NULL,
    contract_details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS subcontractor_projects (
    id INT AUTO_INCREMENT PRIMARY KEY,
    subcontractor_id INT NOT NULL,
    project_id INT NOT NULL,
    FOREIGN KEY (subcontractor_id) REFERENCES subcontractors(subcontractor_id),
    FOREIGN KEY (project_id) REFERENCES projects(project_id),
    UNIQUE KEY (subcontractor_id, project_id)
);

INSERT INTO users (username, password_hash, full_name, email, role)
VALUES ('admin', 'hashed_password', 'Admin User', 'admin@example.com', 'admin');
"""

# Connect to MySQL and execute
try:
    connection = mysql.connector.connect(
        host='192.168.0.174',       # or '127.0.0.1'
        user='remote_control',   # replace with your MySQL username
        password='Remote_control' # replace with your MySQL password
    )

    if connection.is_connected():
        print("Connected to MySQL Server")
        cursor = connection.cursor()
        for statement in sql_script.strip().split(';'):
            if statement.strip():
                cursor.execute(statement + ';')
        print("Database and tables created successfully.")
        connection.commit()

except Error as e:
    print("Error:", e)

finally:
    if connection.is_connected():
        cursor.close()
        connection.close()
        print("MySQL connection closed.")
