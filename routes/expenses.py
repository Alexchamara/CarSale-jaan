from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import extract, func

from models import Expense, db
from utils import log_action

expenses_bp = Blueprint('expenses', __name__)

PAYMENT_METHODS = ['Cash', 'Bank', 'Cheque']
HIGH_EXPENSE_THRESHOLD = Decimal('50000.00')


def require_perm(action):
    if not current_user.has_permission('expenses', action):
        flash('You do not have permission for this action.', 'danger')
        return False
    return True


def parse_date(value, fallback=None):
    if not value:
        return fallback
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return fallback


def parse_amount(value):
    try:
        amt = Decimal((value or '').strip())
    except (InvalidOperation, AttributeError):
        return None
    return amt.quantize(Decimal('0.01'))


def sum_expenses(rows):
    total = Decimal('0.00')
    for row in rows:
        total += Decimal(row.amount or 0)
    return total


@expenses_bp.route('/')
@login_required
def list_expenses():
    if not require_perm('view'):
        return redirect(url_for('reports.dashboard'))

    today = date.today()
    date_from_str = (request.args.get('date_from') or today.isoformat()).strip()
    date_to_str = (request.args.get('date_to') or today.isoformat()).strip()
    payment_method_filter = (request.args.get('payment_method') or '').strip()

    date_from = parse_date(date_from_str, today)
    date_to = parse_date(date_to_str, today)

    if date_from > date_to:
        flash('From date must be before To date.', 'danger')
        date_from = today
        date_to = today
        date_from_str = today.isoformat()
        date_to_str = today.isoformat()

    query = Expense.query
    query = query.filter(Expense.expense_date >= date_from, Expense.expense_date <= date_to)
    if payment_method_filter:
        query = query.filter(Expense.payment_method == payment_method_filter)
    expenses = query.order_by(Expense.expense_date.desc(), Expense.id.desc()).all()
    filtered_total = sum_expenses(expenses)
    is_today_default = (
        date_from_str == today.isoformat() and
        date_to_str == today.isoformat() and
        not payment_method_filter
    )

    return render_template(
        'admin/expenses/list.html',
        expenses=expenses,
        filtered_total=filtered_total,
        is_today_default=is_today_default,
        date_from_str=date_from_str,
        date_to_str=date_to_str,
        payment_method_filter=payment_method_filter,
        payment_methods=PAYMENT_METHODS,
        high_expense_threshold=HIGH_EXPENSE_THRESHOLD,
    )


@expenses_bp.route('/report/last-7-days')
@login_required
def report_last_7_days():
    if not require_perm('view'):
        return jsonify({'ok': False, 'message': 'Forbidden'}), 403

    today = date.today()
    week_start = today - timedelta(days=6)
    rows = Expense.query.filter(
        Expense.expense_date >= week_start,
        Expense.expense_date <= today,
    ).order_by(Expense.expense_date.desc(), Expense.id.desc()).all()

    total = sum_expenses(rows)
    payload = [
        {
            'date': r.expense_date.strftime('%d %b %Y'),
            'description': r.description,
            'amount': float(r.amount or 0),
            'payment_method': r.payment_method,
        }
        for r in rows
    ]
    return jsonify({'ok': True, 'rows': payload, 'total': float(total)})


@expenses_bp.route('/report/weekly')
@login_required
def report_weekly():
    if not require_perm('view'):
        return jsonify({'ok': False, 'message': 'Forbidden'}), 403

    rows = (
        db.session.query(
            func.strftime('%Y-W%W', Expense.expense_date).label('week_key'),
            func.min(Expense.expense_date).label('week_start'),
            func.max(Expense.expense_date).label('week_end'),
            func.count(Expense.id).label('entry_count'),
            func.sum(Expense.amount).label('total_amount'),
        )
        .group_by(func.strftime('%Y-W%W', Expense.expense_date))
        .order_by(func.strftime('%Y-W%W', Expense.expense_date).desc())
        .limit(12)
        .all()
    )

    grand_total = Decimal('0.00')
    payload = []
    for r in rows:
        total_amount = Decimal(r.total_amount or 0)
        grand_total += total_amount
        payload.append({
            'week_key': r.week_key,
            'week_start': r.week_start.strftime('%d %b %Y') if r.week_start else '',
            'week_end': r.week_end.strftime('%d %b %Y') if r.week_end else '',
            'entry_count': int(r.entry_count or 0),
            'total_amount': float(total_amount),
        })

    return jsonify({'ok': True, 'rows': payload, 'grand_total': float(grand_total)})


@expenses_bp.route('/report/monthly')
@login_required
def report_monthly():
    if not require_perm('view'):
        return jsonify({'ok': False, 'message': 'Forbidden'}), 403

    rows = (
        db.session.query(
            func.strftime('%Y-%m', Expense.expense_date).label('month_key'),
            func.count(Expense.id).label('entry_count'),
            func.sum(Expense.amount).label('total_amount'),
        )
        .group_by(func.strftime('%Y-%m', Expense.expense_date))
        .order_by(func.strftime('%Y-%m', Expense.expense_date).desc())
        .limit(12)
        .all()
    )

    grand_total = Decimal('0.00')
    payload = []
    for r in rows:
        total_amount = Decimal(r.total_amount or 0)
        grand_total += total_amount
        payload.append({
            'month_key': r.month_key,
            'entry_count': int(r.entry_count or 0),
            'total_amount': float(total_amount),
        })

    return jsonify({'ok': True, 'rows': payload, 'grand_total': float(grand_total)})


@expenses_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_expense():
    if not require_perm('create'):
        return redirect(url_for('expenses.list_expenses'))

    if request.method == 'POST':
        expense_date = parse_date(request.form.get('expense_date'), None)
        description = (request.form.get('description') or '').strip()
        amount = parse_amount(request.form.get('amount'))
        payment_method = (request.form.get('payment_method') or '').strip()

        if not expense_date or not description or not amount or not payment_method:
            flash('All fields are required.', 'danger')
            return render_template(
                'admin/expenses/form.html',
                expense=None,
                payment_methods=PAYMENT_METHODS,
                today_str=date.today().isoformat(),
            )

        if payment_method not in PAYMENT_METHODS:
            flash('Invalid payment method selected.', 'danger')
            return redirect(url_for('expenses.new_expense'))

        if amount <= 0:
            flash('Amount must be greater than zero.', 'danger')
            return redirect(url_for('expenses.new_expense'))

        expense = Expense(
            expense_date=expense_date,
            description=description,
            amount=amount,
            payment_method=payment_method,
        )
        db.session.add(expense)
        db.session.commit()
        log_action(current_user.id, 'create', 'expenses', expense.id, f'Created expense - {amount}')
        flash('Expense saved successfully.', 'success')
        return redirect(url_for('expenses.list_expenses'))

    return render_template(
        'admin/expenses/form.html',
        expense=None,
        payment_methods=PAYMENT_METHODS,
        today_str=date.today().isoformat(),
    )


@expenses_bp.route('/<int:expense_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    if not require_perm('edit'):
        return redirect(url_for('expenses.list_expenses'))

    if request.method == 'POST':
        expense_date = parse_date(request.form.get('expense_date'), None)
        description = (request.form.get('description') or '').strip()
        amount = parse_amount(request.form.get('amount'))
        payment_method = (request.form.get('payment_method') or '').strip()

        if not expense_date or not description or not amount or not payment_method:
            flash('All fields are required.', 'danger')
            return redirect(url_for('expenses.edit_expense', expense_id=expense.id))

        if payment_method not in PAYMENT_METHODS:
            flash('Invalid payment method selected.', 'danger')
            return redirect(url_for('expenses.edit_expense', expense_id=expense.id))

        if amount <= 0:
            flash('Amount must be greater than zero.', 'danger')
            return redirect(url_for('expenses.edit_expense', expense_id=expense.id))

        expense.expense_date = expense_date
        expense.description = description
        expense.amount = amount
        expense.payment_method = payment_method

        db.session.commit()
        log_action(current_user.id, 'edit', 'expenses', expense.id, f'Updated expense - {amount}')
        flash('Expense updated successfully.', 'success')
        return redirect(url_for('expenses.list_expenses'))

    return render_template(
        'admin/expenses/form.html',
        expense=expense,
        payment_methods=PAYMENT_METHODS,
        today_str=date.today().isoformat(),
    )


@expenses_bp.route('/<int:expense_id>/delete', methods=['POST'])
@login_required
def delete_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    if not require_perm('delete'):
        return redirect(url_for('expenses.list_expenses'))

    db.session.delete(expense)
    db.session.commit()
    log_action(current_user.id, 'delete', 'expenses', expense.id, f'Deleted expense - {expense.amount}')
    flash('Expense deleted successfully.', 'success')
    return redirect(url_for('expenses.list_expenses'))
