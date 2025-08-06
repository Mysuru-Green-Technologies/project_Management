CREATE DATABASE IF NOT EXISTS construction_project_management;
USE construction_project_management;

-- Users table
CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    role ENUM('admin', 'manager', 'supervisor', 'worker') NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Projects table
CREATE TABLE projects (
    project_id INT AUTO_INCREMENT PRIMARY KEY,
    project_name VARCHAR(100) NOT NULL,
    description TEXT,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    estimated_budget DECIMAL(15,2),
    actual_budget DECIMAL(15,2) DEFAULT 0,
    status ENUM('planned', 'in_progress', 'on_hold', 'completed', 'cancelled') DEFAULT 'planned',
    created_by INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (created_by) REFERENCES users(user_id)
);

-- Tasks table
CREATE TABLE tasks (
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

-- Workers table
CREATE TABLE workers (
    worker_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    contact_number VARCHAR(20),
    email VARCHAR(100),
    specialization VARCHAR(100),
    daily_wage DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Task assignments table
CREATE TABLE task_assignments (
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

-- Materials table
CREATE TABLE materials (
    material_id INT AUTO_INCREMENT PRIMARY KEY,
    material_name VARCHAR(100) NOT NULL,
    unit VARCHAR(20) NOT NULL,
    unit_cost DECIMAL(10,2) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Task materials table
CREATE TABLE task_materials (
    task_material_id INT AUTO_INCREMENT PRIMARY KEY,
    task_id INT NOT NULL,
    material_id INT NOT NULL,
    quantity DECIMAL(10,2) NOT NULL,
    total_cost DECIMAL(15,2) GENERATED ALWAYS AS (quantity * (SELECT unit_cost FROM materials WHERE material_id = task_materials.material_id)) STORED,
    date_used DATE NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id),
    FOREIGN KEY (material_id) REFERENCES materials(material_id)
);

-- Daily progress table
CREATE TABLE daily_progress (
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