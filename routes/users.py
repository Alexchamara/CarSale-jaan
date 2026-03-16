from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, User
from utils import log_action

users_bp = Blueprint('users', __name__)

ROLES = ['admin', 'sales_manager', 'sales_executive', 'accounts', 'viewer']


@users_bp.route('/')
@login_required
def list_users():
    if not current_user.has_permission('users', 'view'):
        flash('Permission denied.', 'danger')
        return redirect(url_for('admin_home'))
    users = User.query.order_by(User.name).all()
    return render_template('admin/users/list.html', users=users, roles=ROLES)


@users_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_user():
    if not current_user.has_permission('users', 'create'):
        flash('Permission denied.', 'danger')
        return redirect(url_for('users.list_users'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        email = request.form.get('email', '').strip().lower()
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return render_template('admin/users/form.html', user=None, roles=ROLES)
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('admin/users/form.html', user=None, roles=ROLES)
        u = User(
            name=request.form.get('name', '').strip(),
            username=username, email=email,
            role=request.form.get('role', 'viewer'),
            phone=request.form.get('phone', '').strip(),
        )
        u.set_password(request.form.get('password', 'changeme123'))
        db.session.add(u)
        db.session.commit()
        log_action(current_user.id, 'create', 'users', u.id, f'Created user {u.username}')
        flash(f'User {u.name} created successfully.', 'success')
        return redirect(url_for('users.list_users'))
    return render_template('admin/users/form.html', user=None, roles=ROLES)


@users_bp.route('/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if not current_user.has_permission('users', 'edit'):
        flash('Permission denied.', 'danger')
        return redirect(url_for('users.list_users'))
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        user.name = request.form.get('name', '').strip()
        user.email = request.form.get('email', '').strip().lower()
        user.role = request.form.get('role', user.role)
        user.phone = request.form.get('phone', '').strip()
        new_password = request.form.get('new_password', '').strip()
        if new_password:
            user.set_password(new_password)
        db.session.commit()
        log_action(current_user.id, 'update', 'users', user.id, f'Updated user {user.username}')
        flash('User updated.', 'success')
        return redirect(url_for('users.list_users'))
    return render_template('admin/users/form.html', user=user, roles=ROLES)


@users_bp.route('/<int:user_id>/toggle', methods=['POST'])
@login_required
def toggle_user(user_id):
    if not current_user.has_permission('users', 'edit'):
        flash('Permission denied.', 'danger')
        return redirect(url_for('users.list_users'))
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot deactivate yourself.', 'warning')
    else:
        user.is_active = not user.is_active
        db.session.commit()
        status = 'activated' if user.is_active else 'deactivated'
        flash(f'User {status}.', 'success')
    return redirect(url_for('users.list_users'))
