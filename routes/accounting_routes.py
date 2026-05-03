from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from sqlalchemy import func

from models import db
from models.user import User
from models.account import Account, ACCOUNT_TYPES
from models.journal import JournalEntry, JournalLine
from models.customer import Customer
from models.vendor import Vendor
from models.invoice import Invoice, InvoiceLine
from models.expense import Expense
from models.payment import Payment
from utils.decorators import accountant_required, admin_required
from utils.helpers import next_number

main_bp = Blueprint('main', __name__)
accounting_bp = Blueprint('accounting', __name__)

# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------

@main_bp.route('/')
@main_bp.route('/dashboard')
@login_required
def dashboard():
    # Revenue total (all Revenue accounts)
    revenue_accounts = Account.query.filter_by(account_type='Revenue', is_active=True).all()
    total_revenue = sum(acc.balance for acc in revenue_accounts)

    # Expense total (all Expense accounts)
    expense_accounts = Account.query.filter_by(account_type='Expense', is_active=True).all()
    total_expenses = sum(acc.balance for acc in expense_accounts)

    net_profit = total_revenue - total_expenses

    # Outstanding receivables
    unpaid_invoices = Invoice.query.filter(Invoice.status.in_(['unpaid', 'partial'])).all()
    outstanding_receivables = sum(inv.balance_due for inv in unpaid_invoices)

    # Outstanding payables
    unpaid_expenses = Expense.query.filter_by(status='unpaid').all()
    outstanding_payables = sum(float(exp.amount) for exp in unpaid_expenses)

    total_users = None
    if current_user.role == 'admin':
        total_users = User.query.count()

    # Cash balance (account code 1000)
    cash_account = Account.query.filter_by(code='1000').first()
    cash_balance = cash_account.balance if cash_account else 0

    recent_entries = JournalEntry.query.order_by(JournalEntry.created_at.desc()).limit(10).all()
    recent_invoices = Invoice.query.order_by(Invoice.created_at.desc()).limit(5).all()
    pending_invoices = Invoice.query.filter(Invoice.status.in_(['unpaid', 'partial'])).count()

    return render_template('dashboard.html',
                           total_revenue=total_revenue,
                           total_expenses=total_expenses,
                           net_profit=net_profit,
                           outstanding_receivables=outstanding_receivables,
                           outstanding_payables=outstanding_payables,
                           total_users=total_users,
                           cash_balance=cash_balance,
                           recent_entries=recent_entries,
                           recent_invoices=recent_invoices,
                           pending_invoices=pending_invoices)


# ---------------------------------------------------------------------------
# CHART OF ACCOUNTS
# ---------------------------------------------------------------------------

@accounting_bp.route('/accounts')
@login_required
def accounts():
    account_type_filter = request.args.get('type', '')
    query = Account.query
    if account_type_filter and account_type_filter in ACCOUNT_TYPES:
        query = query.filter_by(account_type=account_type_filter)
    all_accounts = query.order_by(Account.code).all()
    return render_template('accounting/accounts.html',
                           accounts=all_accounts,
                           account_types=ACCOUNT_TYPES,
                           current_type=account_type_filter)


@accounting_bp.route('/accounts/create', methods=['GET', 'POST'])
@login_required
@accountant_required
def create_account():
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        name = request.form.get('name', '').strip()
        account_type = request.form.get('account_type', '')
        description = request.form.get('description', '').strip()

        errors = []
        if not code:
            errors.append('Account code is required.')
        if not name:
            errors.append('Account name is required.')
        if account_type not in ACCOUNT_TYPES:
            errors.append('Invalid account type.')
        if Account.query.filter_by(code=code).first():
            errors.append(f'Account code "{code}" already exists.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('accounting/account_form.html', action='Create',
                                   account=None, account_types=ACCOUNT_TYPES,
                                   form_data=request.form)

        account = Account(code=code, name=name, account_type=account_type, description=description)
        db.session.add(account)
        db.session.commit()
        flash(f'Account "{code} - {name}" created successfully.', 'success')
        return redirect(url_for('accounting.accounts'))

    return render_template('accounting/account_form.html', action='Create',
                           account=None, account_types=ACCOUNT_TYPES, form_data={})


@accounting_bp.route('/accounts/<int:account_id>/edit', methods=['GET', 'POST'])
@login_required
@accountant_required
def edit_account(account_id):
    account = Account.query.get_or_404(account_id)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        account_type = request.form.get('account_type', '')
        description = request.form.get('description', '').strip()

        if not name:
            flash('Account name is required.', 'danger')
            return render_template('accounting/account_form.html', action='Edit',
                                   account=account, account_types=ACCOUNT_TYPES,
                                   form_data=request.form)

        account.name = name
        account.account_type = account_type
        account.description = description
        db.session.commit()
        flash('Account updated successfully.', 'success')
        return redirect(url_for('accounting.accounts'))

    return render_template('accounting/account_form.html', action='Edit',
                           account=account, account_types=ACCOUNT_TYPES,
                           form_data={'name': account.name, 'account_type': account.account_type,
                                      'description': account.description or ''})


@accounting_bp.route('/accounts/<int:account_id>/toggle-active', methods=['POST'])
@login_required
@accountant_required
def toggle_account_active(account_id):
    account = Account.query.get_or_404(account_id)
    account.is_active = not account.is_active
    db.session.commit()
    status = 'activated' if account.is_active else 'deactivated'
    flash(f'Account "{account.name}" has been {status}.', 'success')
    return redirect(url_for('accounting.accounts'))


# ---------------------------------------------------------------------------
# JOURNAL ENTRIES
# ---------------------------------------------------------------------------

@accounting_bp.route('/journal')
@login_required
def journal_entries():
    entries = JournalEntry.query.order_by(JournalEntry.date.desc(), JournalEntry.id.desc()).all()
    return render_template('accounting/journal_entries.html', entries=entries)


@accounting_bp.route('/journal/create', methods=['GET', 'POST'])
@login_required
@accountant_required
def create_journal_entry():
    active_accounts = Account.query.filter_by(is_active=True).order_by(Account.code).all()

    if request.method == 'POST':
        entry_date = request.form.get('date', '')
        description = request.form.get('description', '').strip()
        reference = request.form.get('reference', '').strip()

        # Parse lines
        account_ids = request.form.getlist('account_id[]')
        descriptions = request.form.getlist('line_description[]')
        debits = request.form.getlist('debit[]')
        credits = request.form.getlist('credit[]')

        errors = []
        if not entry_date:
            errors.append('Date is required.')
        if not description:
            errors.append('Description is required.')

        # Build valid lines
        valid_lines = []
        for i in range(len(account_ids)):
            acc_id = account_ids[i].strip() if i < len(account_ids) else ''
            dr_str = debits[i].strip() if i < len(debits) else '0'
            cr_str = credits[i].strip() if i < len(credits) else '0'

            if not acc_id:
                continue

            try:
                dr = Decimal(dr_str or '0')
                cr = Decimal(cr_str or '0')
            except InvalidOperation:
                errors.append(f'Invalid amount on line {i + 1}.')
                continue

            if dr < 0 or cr < 0:
                errors.append(f'Amounts cannot be negative on line {i + 1}.')
                continue

            if dr == 0 and cr == 0:
                continue

            account = Account.query.get(int(acc_id))
            if not account:
                errors.append(f'Invalid account on line {i + 1}.')
                continue
            if not account.is_active:
                errors.append(f'Account "{account.name}" is inactive and cannot receive transactions.')
                continue

            valid_lines.append({
                'account_id': int(acc_id),
                'description': descriptions[i].strip() if i < len(descriptions) else '',
                'debit': dr,
                'credit': cr
            })

        if not valid_lines:
            errors.append('At least one journal line is required.')

        if not errors:
            total_dr = sum(l['debit'] for l in valid_lines)
            total_cr = sum(l['credit'] for l in valid_lines)
            if abs(total_dr - total_cr) >= Decimal('0.01'):
                errors.append(
                    f'Journal entry is unbalanced. Total Debits: {total_dr:.2f}, Total Credits: {total_cr:.2f}'
                )

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('accounting/journal_create.html',
                                   accounts=active_accounts, form_data=request.form,
                                   today=date.today().isoformat())

        entry_number = next_number(JournalEntry, 'entry_number', 'JE')
        entry = JournalEntry(
            entry_number=entry_number,
            date=datetime.strptime(entry_date, '%Y-%m-%d').date(),
            description=description,
            reference=reference or None,
            created_by=current_user.id
        )
        db.session.add(entry)
        db.session.flush()

        for l in valid_lines:
            line = JournalLine(
                journal_entry_id=entry.id,
                account_id=l['account_id'],
                description=l['description'] or None,
                debit=l['debit'],
                credit=l['credit']
            )
            db.session.add(line)

        db.session.commit()
        flash(f'Journal entry {entry_number} posted successfully.', 'success')
        return redirect(url_for('accounting.journal_detail', entry_id=entry.id))

    return render_template('accounting/journal_create.html',
                           accounts=active_accounts, form_data={},
                           today=date.today().isoformat())


@accounting_bp.route('/journal/<int:entry_id>')
@login_required
def journal_detail(entry_id):
    entry = JournalEntry.query.get_or_404(entry_id)
    return render_template('accounting/journal_detail.html', entry=entry)


@accounting_bp.route('/journal/<int:entry_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_journal_entry(entry_id):
    entry = JournalEntry.query.get_or_404(entry_id)
    number = entry.entry_number
    db.session.delete(entry)
    db.session.commit()
    flash(f'Journal entry {number} has been deleted.', 'success')
    return redirect(url_for('accounting.journal_entries'))


# ---------------------------------------------------------------------------
# CUSTOMERS
# ---------------------------------------------------------------------------

@accounting_bp.route('/customers')
@login_required
def customers():
    all_customers = Customer.query.order_by(Customer.name).all()
    return render_template('accounting/customers.html', customers=all_customers)


@accounting_bp.route('/customers/create', methods=['GET', 'POST'])
@login_required
@accountant_required
def create_customer():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Customer name is required.', 'danger')
            return render_template('accounting/customer_form.html', action='Create',
                                   customer=None, form_data=request.form)

        customer = Customer(
            name=name,
            email=request.form.get('email', '').strip() or None,
            phone=request.form.get('phone', '').strip() or None,
            address=request.form.get('address', '').strip() or None,
            company=request.form.get('company', '').strip() or None,
            notes=request.form.get('notes', '').strip() or None
        )
        db.session.add(customer)
        db.session.commit()
        flash(f'Customer "{name}" created successfully.', 'success')
        return redirect(url_for('accounting.customers'))

    return render_template('accounting/customer_form.html', action='Create',
                           customer=None, form_data={})


@accounting_bp.route('/customers/<int:customer_id>/edit', methods=['GET', 'POST'])
@login_required
@accountant_required
def edit_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Customer name is required.', 'danger')
            return render_template('accounting/customer_form.html', action='Edit',
                                   customer=customer, form_data=request.form)

        customer.name = name
        customer.email = request.form.get('email', '').strip() or None
        customer.phone = request.form.get('phone', '').strip() or None
        customer.address = request.form.get('address', '').strip() or None
        customer.company = request.form.get('company', '').strip() or None
        customer.notes = request.form.get('notes', '').strip() or None
        db.session.commit()
        flash('Customer updated successfully.', 'success')
        return redirect(url_for('accounting.customers'))

    return render_template('accounting/customer_form.html', action='Edit',
                           customer=customer, form_data={})


@accounting_bp.route('/customers/<int:customer_id>')
@login_required
def customer_detail(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    return render_template('accounting/customer_detail.html', customer=customer)


# ---------------------------------------------------------------------------
# VENDORS
# ---------------------------------------------------------------------------

@accounting_bp.route('/vendors')
@login_required
def vendors():
    all_vendors = Vendor.query.order_by(Vendor.name).all()
    return render_template('accounting/vendors.html', vendors=all_vendors)


@accounting_bp.route('/vendors/create', methods=['GET', 'POST'])
@login_required
@accountant_required
def create_vendor():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Vendor name is required.', 'danger')
            return render_template('accounting/vendor_form.html', action='Create',
                                   vendor=None, form_data=request.form)

        vendor = Vendor(
            name=name,
            email=request.form.get('email', '').strip() or None,
            phone=request.form.get('phone', '').strip() or None,
            address=request.form.get('address', '').strip() or None,
            company=request.form.get('company', '').strip() or None,
            notes=request.form.get('notes', '').strip() or None
        )
        db.session.add(vendor)
        db.session.commit()
        flash(f'Vendor "{name}" created successfully.', 'success')
        return redirect(url_for('accounting.vendors'))

    return render_template('accounting/vendor_form.html', action='Create',
                           vendor=None, form_data={})


@accounting_bp.route('/vendors/<int:vendor_id>/edit', methods=['GET', 'POST'])
@login_required
@accountant_required
def edit_vendor(vendor_id):
    vendor = Vendor.query.get_or_404(vendor_id)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Vendor name is required.', 'danger')
            return render_template('accounting/vendor_form.html', action='Edit',
                                   vendor=vendor, form_data=request.form)

        vendor.name = name
        vendor.email = request.form.get('email', '').strip() or None
        vendor.phone = request.form.get('phone', '').strip() or None
        vendor.address = request.form.get('address', '').strip() or None
        vendor.company = request.form.get('company', '').strip() or None
        vendor.notes = request.form.get('notes', '').strip() or None
        db.session.commit()
        flash('Vendor updated successfully.', 'success')
        return redirect(url_for('accounting.vendors'))

    return render_template('accounting/vendor_form.html', action='Edit',
                           vendor=vendor, form_data={})


@accounting_bp.route('/vendors/<int:vendor_id>')
@login_required
def vendor_detail(vendor_id):
    vendor = Vendor.query.get_or_404(vendor_id)
    return render_template('accounting/vendor_detail.html', vendor=vendor)


# ---------------------------------------------------------------------------
# INVOICES (Accounts Receivable)
# ---------------------------------------------------------------------------

@accounting_bp.route('/invoices')
@login_required
def invoices():
    status_filter = request.args.get('status', '')
    query = Invoice.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    all_invoices = query.order_by(Invoice.date.desc(), Invoice.id.desc()).all()
    return render_template('accounting/invoices.html', invoices=all_invoices,
                           status_filter=status_filter)


@accounting_bp.route('/invoices/create', methods=['GET', 'POST'])
@login_required
@accountant_required
def create_invoice():
    customers = Customer.query.filter_by(is_active=True).order_by(Customer.name).all()
    revenue_accounts = Account.query.filter_by(
        account_type='Revenue', is_active=True
    ).order_by(Account.code).all()

    if request.method == 'POST':
        customer_id = request.form.get('customer_id', '')
        inv_date = request.form.get('date', '')
        due_date = request.form.get('due_date', '').strip()
        notes = request.form.get('notes', '').strip()

        descriptions = request.form.getlist('description[]')
        quantities = request.form.getlist('quantity[]')
        unit_prices = request.form.getlist('unit_price[]')
        line_account_ids = request.form.getlist('line_account_id[]')

        errors = []
        if not customer_id:
            errors.append('Customer is required.')
        if not inv_date:
            errors.append('Invoice date is required.')

        # Parse lines
        valid_lines = []
        for i in range(len(descriptions)):
            desc = descriptions[i].strip() if i < len(descriptions) else ''
            qty_str = quantities[i].strip() if i < len(quantities) else ''
            price_str = unit_prices[i].strip() if i < len(unit_prices) else ''
            acc_id = line_account_ids[i].strip() if i < len(line_account_ids) else ''

            if not desc and not qty_str and not price_str:
                continue

            if not desc:
                errors.append(f'Description required on line {i + 1}.')
                continue

            try:
                qty = Decimal(qty_str or '1')
                price = Decimal(price_str or '0')
            except InvalidOperation:
                errors.append(f'Invalid quantity or price on line {i + 1}.')
                continue

            if qty <= 0:
                errors.append(f'Quantity must be greater than zero on line {i + 1}.')
                continue
            if price < 0:
                errors.append(f'Unit price cannot be negative on line {i + 1}.')
                continue

            valid_lines.append({
                'description': desc,
                'quantity': qty,
                'unit_price': price,
                'account_id': int(acc_id) if acc_id else None
            })

        if not valid_lines:
            errors.append('At least one line item is required.')

        total = sum(float(l['quantity']) * float(l['unit_price']) for l in valid_lines)
        if total <= 0:
            errors.append('Invoice total must be greater than zero.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('accounting/invoice_create.html',
                                   customers=customers, revenue_accounts=revenue_accounts,
                                   form_data=request.form, today=date.today().isoformat())

        inv_number = next_number(Invoice, 'invoice_number', 'INV')
        invoice = Invoice(
            invoice_number=inv_number,
            customer_id=int(customer_id),
            date=datetime.strptime(inv_date, '%Y-%m-%d').date(),
            due_date=datetime.strptime(due_date, '%Y-%m-%d').date() if due_date else None,
            notes=notes or None,
            status='unpaid',
            created_by=current_user.id
        )
        db.session.add(invoice)
        db.session.flush()

        for l in valid_lines:
            line = InvoiceLine(
                invoice_id=invoice.id,
                description=l['description'],
                quantity=l['quantity'],
                unit_price=l['unit_price'],
                account_id=l['account_id']
            )
            db.session.add(line)

        # Auto-create journal entry: Dr Accounts Receivable / Cr Revenue
        ar_account = Account.query.filter_by(code='1100').first()
        rev_account = Account.query.filter_by(code='4000').first()

        if ar_account and rev_account:
            je_number = next_number(JournalEntry, 'entry_number', 'JE')
            je = JournalEntry(
                entry_number=je_number,
                date=invoice.date,
                description=f'Invoice {inv_number} - {invoice.customer.name}',
                reference=inv_number,
                created_by=current_user.id
            )
            db.session.add(je)
            db.session.flush()
            db.session.add(JournalLine(journal_entry_id=je.id, account_id=ar_account.id,
                                       debit=Decimal(str(total)), credit=0))
            db.session.add(JournalLine(journal_entry_id=je.id, account_id=rev_account.id,
                                       debit=0, credit=Decimal(str(total))))

        db.session.commit()
        flash(f'Invoice {inv_number} created successfully.', 'success')
        return redirect(url_for('accounting.invoice_detail', invoice_id=invoice.id))

    return render_template('accounting/invoice_create.html',
                           customers=customers, revenue_accounts=revenue_accounts,
                           form_data={}, today=date.today().isoformat())


@accounting_bp.route('/invoices/<int:invoice_id>')
@login_required
def invoice_detail(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    return render_template('accounting/invoice_detail.html', invoice=invoice)


@accounting_bp.route('/invoices/<int:invoice_id>/mark-paid', methods=['POST'])
@login_required
@accountant_required
def mark_invoice_paid(invoice_id):
    invoice = Invoice.query.get_or_404(invoice_id)
    if invoice.status == 'paid':
        flash('Invoice is already marked as paid.', 'info')
        return redirect(url_for('accounting.invoice_detail', invoice_id=invoice_id))

    # Record full payment
    cash_account = Account.query.filter_by(code='1000').first()
    ar_account = Account.query.filter_by(code='1100').first()
    amount = invoice.balance_due

    pay_number = next_number(Payment, 'payment_number', 'PAY')
    payment = Payment(
        payment_number=pay_number,
        payment_type='invoice',
        invoice_id=invoice.id,
        amount=Decimal(str(amount)),
        date=date.today(),
        account_id=cash_account.id if cash_account else None,
        notes=f'Full payment for invoice {invoice.invoice_number}',
        created_by=current_user.id
    )
    db.session.add(payment)

    invoice.status = 'paid'

    # Journal entry: Dr Cash / Cr AR
    if cash_account and ar_account:
        je_number = next_number(JournalEntry, 'entry_number', 'JE')
        je = JournalEntry(
            entry_number=je_number,
            date=date.today(),
            description=f'Payment received - Invoice {invoice.invoice_number}',
            reference=pay_number,
            created_by=current_user.id
        )
        db.session.add(je)
        db.session.flush()
        db.session.add(JournalLine(journal_entry_id=je.id, account_id=cash_account.id,
                                   debit=Decimal(str(amount)), credit=0))
        db.session.add(JournalLine(journal_entry_id=je.id, account_id=ar_account.id,
                                   debit=0, credit=Decimal(str(amount))))

    db.session.commit()
    flash(f'Invoice {invoice.invoice_number} marked as paid.', 'success')
    return redirect(url_for('accounting.invoice_detail', invoice_id=invoice_id))


# ---------------------------------------------------------------------------
# EXPENSES (Accounts Payable)
# ---------------------------------------------------------------------------

@accounting_bp.route('/expenses')
@login_required
def expenses():
    status_filter = request.args.get('status', '')
    query = Expense.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    all_expenses = query.order_by(Expense.date.desc(), Expense.id.desc()).all()
    return render_template('accounting/expenses.html', expenses=all_expenses,
                           status_filter=status_filter)


@accounting_bp.route('/expenses/create', methods=['GET', 'POST'])
@login_required
@accountant_required
def create_expense():
    vendors = Vendor.query.filter_by(is_active=True).order_by(Vendor.name).all()
    expense_accounts = Account.query.filter_by(
        account_type='Expense', is_active=True
    ).order_by(Account.code).all()

    if request.method == 'POST':
        vendor_id = request.form.get('vendor_id', '').strip()
        account_id = request.form.get('account_id', '').strip()
        exp_date = request.form.get('date', '').strip()
        amount_str = request.form.get('amount', '').strip()
        description = request.form.get('description', '').strip()
        reference = request.form.get('reference', '').strip()

        errors = []
        if not account_id:
            errors.append('Expense account is required.')
        if not exp_date:
            errors.append('Date is required.')
        if not description:
            errors.append('Description is required.')

        try:
            amount = Decimal(amount_str or '0')
        except InvalidOperation:
            errors.append('Invalid amount.')
            amount = Decimal('0')

        if amount <= 0:
            errors.append('Amount must be greater than zero.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('accounting/expense_form.html',
                                   vendors=vendors, expense_accounts=expense_accounts,
                                   form_data=request.form, today=date.today().isoformat())

        exp_number = next_number(Expense, 'expense_number', 'EXP')
        expense = Expense(
            expense_number=exp_number,
            vendor_id=int(vendor_id) if vendor_id else None,
            account_id=int(account_id),
            date=datetime.strptime(exp_date, '%Y-%m-%d').date(),
            amount=amount,
            description=description,
            reference=reference or None,
            status='unpaid',
            created_by=current_user.id
        )
        db.session.add(expense)
        db.session.flush()

        # Journal entry: Dr Expense / Cr Accounts Payable
        ap_account = Account.query.filter_by(code='2000').first()
        exp_account = Account.query.get(int(account_id))

        if ap_account and exp_account:
            je_number = next_number(JournalEntry, 'entry_number', 'JE')
            je = JournalEntry(
                entry_number=je_number,
                date=expense.date,
                description=f'Expense {exp_number} - {description}',
                reference=exp_number,
                created_by=current_user.id
            )
            db.session.add(je)
            db.session.flush()
            db.session.add(JournalLine(journal_entry_id=je.id, account_id=exp_account.id,
                                       debit=amount, credit=0))
            db.session.add(JournalLine(journal_entry_id=je.id, account_id=ap_account.id,
                                       debit=0, credit=amount))

        db.session.commit()
        flash(f'Expense {exp_number} recorded successfully.', 'success')
        return redirect(url_for('accounting.expenses'))

    return render_template('accounting/expense_form.html',
                           vendors=vendors, expense_accounts=expense_accounts,
                           form_data={}, today=date.today().isoformat())


@accounting_bp.route('/expenses/<int:expense_id>/pay', methods=['POST'])
@login_required
@accountant_required
def pay_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    if expense.status == 'paid':
        flash('Expense is already paid.', 'info')
        return redirect(url_for('accounting.expenses'))

    cash_account = Account.query.filter_by(code='1000').first()
    ap_account = Account.query.filter_by(code='2000').first()
    amount = expense.balance_due

    pay_number = next_number(Payment, 'payment_number', 'PAY')
    payment = Payment(
        payment_number=pay_number,
        payment_type='expense',
        expense_id=expense.id,
        amount=Decimal(str(amount)),
        date=date.today(),
        account_id=cash_account.id if cash_account else None,
        notes=f'Payment for expense {expense.expense_number}',
        created_by=current_user.id
    )
    db.session.add(payment)
    expense.status = 'paid'

    # Journal: Dr AP / Cr Cash
    if cash_account and ap_account:
        je_number = next_number(JournalEntry, 'entry_number', 'JE')
        je = JournalEntry(
            entry_number=je_number,
            date=date.today(),
            description=f'Payment - Expense {expense.expense_number}',
            reference=pay_number,
            created_by=current_user.id
        )
        db.session.add(je)
        db.session.flush()
        db.session.add(JournalLine(journal_entry_id=je.id, account_id=ap_account.id,
                                   debit=Decimal(str(amount)), credit=0))
        db.session.add(JournalLine(journal_entry_id=je.id, account_id=cash_account.id,
                                   debit=0, credit=Decimal(str(amount))))

    db.session.commit()
    flash(f'Expense {expense.expense_number} marked as paid.', 'success')
    return redirect(url_for('accounting.expenses'))


# ---------------------------------------------------------------------------
# PAYMENTS
# ---------------------------------------------------------------------------

@accounting_bp.route('/payments')
@login_required
def payments():
    all_payments = Payment.query.order_by(Payment.date.desc(), Payment.id.desc()).all()
    return render_template('accounting/payments.html', payments=all_payments)


@accounting_bp.route('/payments/create', methods=['GET', 'POST'])
@login_required
@accountant_required
def create_payment():
    unpaid_invoices = Invoice.query.filter(Invoice.status.in_(['unpaid', 'partial'])).order_by(
        Invoice.invoice_number
    ).all()
    unpaid_expenses = Expense.query.filter_by(status='unpaid').order_by(
        Expense.expense_number
    ).all()
    cash_accounts = Account.query.filter(
        Account.account_type == 'Asset',
        Account.is_active == True
    ).order_by(Account.code).all()

    if request.method == 'POST':
        payment_type = request.form.get('payment_type', '')
        ref_id = request.form.get('reference_id', '').strip()
        amount_str = request.form.get('amount', '').strip()
        pay_date = request.form.get('date', '').strip()
        account_id = request.form.get('account_id', '').strip()
        notes = request.form.get('notes', '').strip()

        errors = []
        if payment_type not in ('invoice', 'expense'):
            errors.append('Payment type is required.')
        if not ref_id:
            errors.append('Please select an invoice or expense.')
        if not pay_date:
            errors.append('Payment date is required.')

        try:
            amount = Decimal(amount_str or '0')
        except InvalidOperation:
            errors.append('Invalid amount.')
            amount = Decimal('0')

        if amount <= 0:
            errors.append('Amount must be greater than zero.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('accounting/payment_form.html',
                                   unpaid_invoices=unpaid_invoices,
                                   unpaid_expenses=unpaid_expenses,
                                   cash_accounts=cash_accounts,
                                   form_data=request.form,
                                   today=date.today().isoformat())

        pay_number = next_number(Payment, 'payment_number', 'PAY')
        payment = Payment(
            payment_number=pay_number,
            payment_type=payment_type,
            amount=amount,
            date=datetime.strptime(pay_date, '%Y-%m-%d').date(),
            account_id=int(account_id) if account_id else None,
            notes=notes or None,
            created_by=current_user.id
        )

        cash_account = Account.query.get(int(account_id)) if account_id else None
        ar_account = Account.query.filter_by(code='1100').first()
        ap_account = Account.query.filter_by(code='2000').first()

        if payment_type == 'invoice':
            invoice = Invoice.query.get_or_404(int(ref_id))
            payment.invoice_id = invoice.id
            if amount >= Decimal(str(invoice.balance_due)):
                invoice.status = 'paid'
            else:
                invoice.status = 'partial'
            # Journal: Dr Cash / Cr AR
            if cash_account and ar_account:
                je_number = next_number(JournalEntry, 'entry_number', 'JE')
                je = JournalEntry(entry_number=je_number, date=payment.date,
                                  description=f'Payment - Invoice {invoice.invoice_number}',
                                  reference=pay_number, created_by=current_user.id)
                db.session.add(je)
                db.session.flush()
                db.session.add(JournalLine(journal_entry_id=je.id, account_id=cash_account.id,
                                           debit=amount, credit=0))
                db.session.add(JournalLine(journal_entry_id=je.id, account_id=ar_account.id,
                                           debit=0, credit=amount))
        else:
            expense = Expense.query.get_or_404(int(ref_id))
            payment.expense_id = expense.id
            if amount >= Decimal(str(expense.balance_due)):
                expense.status = 'paid'
            # Journal: Dr AP / Cr Cash
            if cash_account and ap_account:
                je_number = next_number(JournalEntry, 'entry_number', 'JE')
                je = JournalEntry(entry_number=je_number, date=payment.date,
                                  description=f'Payment - Expense {expense.expense_number}',
                                  reference=pay_number, created_by=current_user.id)
                db.session.add(je)
                db.session.flush()
                db.session.add(JournalLine(journal_entry_id=je.id, account_id=ap_account.id,
                                           debit=amount, credit=0))
                db.session.add(JournalLine(journal_entry_id=je.id, account_id=cash_account.id,
                                           debit=0, credit=amount))

        db.session.add(payment)
        db.session.commit()
        flash(f'Payment {pay_number} recorded successfully.', 'success')
        return redirect(url_for('accounting.payments'))

    return render_template('accounting/payment_form.html',
                           unpaid_invoices=unpaid_invoices,
                           unpaid_expenses=unpaid_expenses,
                           cash_accounts=cash_accounts,
                           form_data={},
                           today=date.today().isoformat())
