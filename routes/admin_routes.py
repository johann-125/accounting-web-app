from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db
from models.user import User
from utils.decorators import admin_required

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/users')
@login_required
@admin_required
def users():
    all_users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=all_users)


@admin_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_user():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        full_name = request.form.get('full_name', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'viewer')

        errors = []
        if not email:
            errors.append('Email is required.')
        if not full_name:
            errors.append('Full name is required.')
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if role not in ('admin', 'accountant', 'manager', 'hr', 'viewer'):
            errors.append('Invalid role selected.')
        if User.query.filter_by(email=email).first():
            errors.append('A user with this email already exists.')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('admin/user_form.html', action='Create', user=None,
                                   form_data=request.form)

        user = User(email=email, full_name=full_name, role=role, is_active=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash(f'User "{full_name}" created successfully.', 'success')
        return redirect(url_for('admin.users'))

    return render_template('admin/user_form.html', action='Create', user=None, form_data={})


@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        role = request.form.get('role', 'viewer')
        new_password = request.form.get('password', '').strip()

        errors = []
        if not full_name:
            errors.append('Full name is required.')
        if not email:
            errors.append('Email is required.')
        existing = User.query.filter_by(email=email).first()
        if existing and existing.id != user_id:
            errors.append('Another user with this email already exists.')
        if new_password and len(new_password) < 6:
            errors.append('Password must be at least 6 characters.')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('admin/user_form.html', action='Edit', user=user,
                                   form_data=request.form)

        user.full_name = full_name
        user.email = email
        user.role = role
        if new_password:
            user.set_password(new_password)

        db.session.commit()
        flash(f'User "{full_name}" updated successfully.', 'success')
        return redirect(url_for('admin.users'))

    return render_template('admin/user_form.html', action='Edit', user=user,
                           form_data={'email': user.email, 'full_name': user.full_name, 'role': user.role})


@admin_bp.route('/users/<int:user_id>/toggle-active', methods=['POST'])
@login_required
@admin_required
def toggle_user_active(user_id):
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash('You cannot deactivate your own account.', 'danger')
        return redirect(url_for('admin.users'))

    if user.role == 'admin' and user.is_active:
        # Check there's at least one other active admin
        active_admins = User.query.filter_by(role='admin', is_active=True).count()
        if active_admins <= 1:
            flash('Cannot deactivate the last active administrator.', 'danger')
            return redirect(url_for('admin.users'))

    user.is_active = not user.is_active
    db.session.commit()
    status = 'activated' if user.is_active else 'deactivated'
    flash(f'User "{user.full_name}" has been {status}.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('admin.users'))

    if user.role == 'admin':
        flash('Administrator accounts cannot be deleted.', 'danger')
        return redirect(url_for('admin.users'))

    name = user.full_name
    db.session.delete(user)
    db.session.commit()
    flash(f'User "{name}" has been permanently deleted.', 'success')
    return redirect(url_for('admin.users'))
