from flask import Blueprint, render_template, request
from flask_login import login_required
from datetime import date, datetime
from sqlalchemy import func

from models import db
from models.account import Account, DEBIT_NORMAL, CREDIT_NORMAL
from models.journal import JournalEntry, JournalLine
from utils.helpers import get_account_balance_for_period

report_bp = Blueprint('reports', __name__, url_prefix='/reports')


def parse_date(date_str):
    """Parse a date string to a date object."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return None


def get_current_year_range():
    today = date.today()
    start = date(today.year, 1, 1)
    end = today
    return start, end


@report_bp.route('/')
@login_required
def index():
    return render_template('reports/index.html')


@report_bp.route('/trial-balance')
@login_required
def trial_balance():
    start_str = request.args.get('start_date', '')
    end_str = request.args.get('end_date', date.today().isoformat())

    start_date = parse_date(start_str)
    end_date = parse_date(end_str) or date.today()

    accounts = Account.query.order_by(Account.code).all()

    rows = []
    total_dr = 0.0
    total_cr = 0.0

    for account in accounts:
        dr, cr, net = get_account_balance_for_period(account, start_date, end_date)
        if dr == 0 and cr == 0:
            continue

        rows.append({
            'code': account.code,
            'name': account.name,
            'type': account.account_type,
            'debit': dr,
            'credit': cr
        })
        total_dr += dr
        total_cr += cr

    balanced = abs(total_dr - total_cr) < 0.01

    return render_template('reports/trial_balance.html',
                           rows=rows,
                           total_dr=total_dr,
                           total_cr=total_cr,
                           balanced=balanced,
                           start_date=start_str,
                           end_date=end_str)


@report_bp.route('/profit-loss')
@login_required
def profit_loss():
    default_start, default_end = get_current_year_range()
    start_str = request.args.get('start_date', default_start.isoformat())
    end_str = request.args.get('end_date', default_end.isoformat())

    start_date = parse_date(start_str) or default_start
    end_date = parse_date(end_str) or default_end

    revenue_accounts = Account.query.filter_by(account_type='Revenue').order_by(Account.code).all()
    expense_accounts = Account.query.filter_by(account_type='Expense').order_by(Account.code).all()

    revenue_rows = []
    total_revenue = 0.0
    for acc in revenue_accounts:
        _, _, net = get_account_balance_for_period(acc, start_date, end_date)
        if net != 0:
            revenue_rows.append({'code': acc.code, 'name': acc.name, 'amount': net})
            total_revenue += net

    expense_rows = []
    total_expenses = 0.0
    for acc in expense_accounts:
        _, _, net = get_account_balance_for_period(acc, start_date, end_date)
        if net != 0:
            expense_rows.append({'code': acc.code, 'name': acc.name, 'amount': net})
            total_expenses += net

    net_profit = total_revenue - total_expenses

    return render_template('reports/profit_loss.html',
                           revenue_rows=revenue_rows,
                           expense_rows=expense_rows,
                           total_revenue=total_revenue,
                           total_expenses=total_expenses,
                           net_profit=net_profit,
                           start_date=start_str,
                           end_date=end_str)


@report_bp.route('/balance-sheet')
@login_required
def balance_sheet():
    as_of_str = request.args.get('as_of', date.today().isoformat())
    as_of_date = parse_date(as_of_str) or date.today()

    asset_accounts = Account.query.filter_by(account_type='Asset').order_by(Account.code).all()
    liability_accounts = Account.query.filter_by(account_type='Liability').order_by(Account.code).all()
    equity_accounts = Account.query.filter_by(account_type='Equity').order_by(Account.code).all()
    revenue_accounts = Account.query.filter_by(account_type='Revenue').order_by(Account.code).all()
    expense_accounts = Account.query.filter_by(account_type='Expense').order_by(Account.code).all()

    def build_rows(accounts):
        rows = []
        total = 0.0
        for acc in accounts:
            _, _, net = get_account_balance_for_period(acc, None, as_of_date)
            rows.append({'code': acc.code, 'name': acc.name, 'amount': net})
            total += net
        return rows, total

    asset_rows, total_assets = build_rows(asset_accounts)
    liability_rows, total_liabilities = build_rows(liability_accounts)
    equity_rows, total_equity_base = build_rows(equity_accounts)

    # Net profit as retained earnings
    total_revenue = sum(
        get_account_balance_for_period(acc, None, as_of_date)[2]
        for acc in revenue_accounts
    )
    total_expense = sum(
        get_account_balance_for_period(acc, None, as_of_date)[2]
        for acc in expense_accounts
    )
    net_income = total_revenue - total_expense

    total_equity = total_equity_base + net_income

    return render_template('reports/balance_sheet.html',
                           asset_rows=asset_rows,
                           liability_rows=liability_rows,
                           equity_rows=equity_rows,
                           total_assets=total_assets,
                           total_liabilities=total_liabilities,
                           total_equity=total_equity,
                           total_equity_base=total_equity_base,
                           net_income=net_income,
                           as_of=as_of_str)


@report_bp.route('/general-ledger')
@login_required
def general_ledger():
    start_str = request.args.get('start_date', '')
    end_str = request.args.get('end_date', date.today().isoformat())
    account_id = request.args.get('account_id', '')

    start_date = parse_date(start_str)
    end_date = parse_date(end_str) or date.today()

    all_accounts = Account.query.order_by(Account.code).all()

    selected_account = None
    ledger_lines = []
    running_balance = 0.0

    if account_id:
        selected_account = Account.query.get(int(account_id))
        if selected_account:
            query = db.session.query(JournalLine, JournalEntry).join(
                JournalEntry, JournalLine.journal_entry_id == JournalEntry.id
            ).filter(
                JournalLine.account_id == selected_account.id
            )
            if start_date:
                query = query.filter(JournalEntry.date >= start_date)
            if end_date:
                query = query.filter(JournalEntry.date <= end_date)

            query = query.order_by(JournalEntry.date, JournalEntry.id)

            from models.account import DEBIT_NORMAL
            for line, entry in query.all():
                dr = float(line.debit)
                cr = float(line.credit)

                if selected_account.account_type in DEBIT_NORMAL:
                    running_balance += dr - cr
                else:
                    running_balance += cr - dr

                ledger_lines.append({
                    'date': entry.date,
                    'entry_number': entry.entry_number,
                    'description': line.description or entry.description,
                    'reference': entry.reference,
                    'debit': dr,
                    'credit': cr,
                    'balance': running_balance
                })

    return render_template('reports/general_ledger.html',
                           all_accounts=all_accounts,
                           selected_account=selected_account,
                           ledger_lines=ledger_lines,
                           start_date=start_str,
                           end_date=end_str,
                           account_id=account_id)
