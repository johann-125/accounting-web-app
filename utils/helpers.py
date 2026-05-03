from models import db


def next_number(model, field, prefix, digits=4):
    """Generate next sequential number for a model (e.g., INV-0001)."""
    last = db.session.query(model).order_by(getattr(model, field).desc()).first()
    if last:
        last_val = getattr(last, field)
        try:
            num = int(last_val.split('-')[-1]) + 1
        except (ValueError, IndexError):
            num = 1
    else:
        num = 1
    return f"{prefix}-{str(num).zfill(digits)}"


def format_currency(amount):
    """Format a number as currency string."""
    try:
        return f"${float(amount):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def get_account_balance_for_period(account, start_date=None, end_date=None):
    """Return (debit_total, credit_total, net_balance) for an account in a date range."""
    from sqlalchemy import func
    from models.journal import JournalLine, JournalEntry
    from models.account import DEBIT_NORMAL

    q_dr = db.session.query(func.sum(JournalLine.debit)).join(JournalEntry).filter(
        JournalLine.account_id == account.id
    )
    q_cr = db.session.query(func.sum(JournalLine.credit)).join(JournalEntry).filter(
        JournalLine.account_id == account.id
    )
    if start_date:
        q_dr = q_dr.filter(JournalEntry.date >= start_date)
        q_cr = q_cr.filter(JournalEntry.date >= start_date)
    if end_date:
        q_dr = q_dr.filter(JournalEntry.date <= end_date)
        q_cr = q_cr.filter(JournalEntry.date <= end_date)

    dr = float(q_dr.scalar() or 0)
    cr = float(q_cr.scalar() or 0)

    if account.account_type in DEBIT_NORMAL:
        net = dr - cr
    else:
        net = cr - dr

    return dr, cr, net
