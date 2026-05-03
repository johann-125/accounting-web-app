"""
AccounTrack – QuickBooks-style Accounting Management System
Flask + SQLite + SQLAlchemy + Flask-Login
"""

from flask import Flask
from flask_login import LoginManager

from config import Config
from models import db
from models.user import User
from models.account import Account


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)

    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please sign in to access this page.'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register Blueprints
    from routes.auth_routes import auth_bp
    from routes.admin_routes import admin_bp
    from routes.accounting_routes import main_bp, accounting_bp
    from routes.report_routes import report_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(accounting_bp)
    app.register_blueprint(report_bp)

    # Context processor – make today available in all templates
    from datetime import date
    @app.context_processor
    def inject_globals():
        return {'today': date.today().isoformat()}

    # Initialize database and seed data
    with app.app_context():
        db.create_all()
        _seed_database(app)

    return app


def _seed_database(app):
    """Create default admin user and chart of accounts on first run."""

    # ---- Admin user ----
    if not User.query.filter_by(email=app.config['ADMIN_EMAIL']).first():
        admin = User(
            email=app.config['ADMIN_EMAIL'],
            full_name=app.config['ADMIN_NAME'],
            role='admin',
            is_active=True
        )
        admin.set_password(app.config['ADMIN_PASSWORD'])
        db.session.add(admin)
        print(f"[INIT] Admin user created: {app.config['ADMIN_EMAIL']}")

    # ---- Default Chart of Accounts ----
    if Account.query.count() == 0:
        default_accounts = [
            # === ASSETS (1xxx) ===
            Account(code='1000', name='Cash and Cash Equivalents',   account_type='Asset',
                    description='Petty cash, bank checking, savings accounts'),
            Account(code='1100', name='Accounts Receivable',         account_type='Asset',
                    description='Amounts owed by customers'),
            Account(code='1200', name='Inventory',                   account_type='Asset',
                    description='Goods available for sale'),
            Account(code='1300', name='Prepaid Expenses',            account_type='Asset',
                    description='Expenses paid in advance'),
            Account(code='1500', name='Equipment',                   account_type='Asset',
                    description='Machinery, computers, office furniture'),
            Account(code='1510', name='Vehicles',                    account_type='Asset',
                    description='Company vehicles'),
            Account(code='1600', name='Accumulated Depreciation',    account_type='Asset',
                    description='Contra-asset: accumulated depreciation on fixed assets'),

            # === LIABILITIES (2xxx) ===
            Account(code='2000', name='Accounts Payable',            account_type='Liability',
                    description='Amounts owed to vendors and suppliers'),
            Account(code='2100', name='Credit Card Payable',         account_type='Liability',
                    description='Outstanding credit card balances'),
            Account(code='2200', name='Accrued Liabilities',         account_type='Liability',
                    description='Expenses incurred but not yet paid'),
            Account(code='2300', name='Sales Tax Payable',           account_type='Liability',
                    description='Sales tax collected but not yet remitted'),
            Account(code='2500', name='Short-term Loans',            account_type='Liability',
                    description='Loans due within one year'),
            Account(code='2800', name='Long-term Loans',             account_type='Liability',
                    description='Loans due beyond one year'),

            # === EQUITY (3xxx) ===
            Account(code='3000', name="Owner's Equity",              account_type='Equity',
                    description='Owner investment and capital contributions'),
            Account(code='3100', name='Retained Earnings',           account_type='Equity',
                    description='Accumulated profits reinvested in the business'),
            Account(code='3200', name="Owner's Draw",                account_type='Equity',
                    description='Withdrawals made by the owner'),

            # === REVENUE (4xxx) ===
            Account(code='4000', name='Sales Revenue',               account_type='Revenue',
                    description='Revenue from product sales'),
            Account(code='4100', name='Service Revenue',             account_type='Revenue',
                    description='Revenue from services rendered'),
            Account(code='4200', name='Interest Income',             account_type='Revenue',
                    description='Interest earned on bank accounts'),
            Account(code='4300', name='Other Income',                account_type='Revenue',
                    description='Miscellaneous income'),

            # === EXPENSES (5xxx) ===
            Account(code='5000', name='Cost of Goods Sold',          account_type='Expense',
                    description='Direct cost of products sold'),
            Account(code='5100', name='Rent Expense',                account_type='Expense',
                    description='Office or shop rental'),
            Account(code='5200', name='Utilities Expense',           account_type='Expense',
                    description='Electricity, water, internet'),
            Account(code='5300', name='Salaries & Wages',            account_type='Expense',
                    description='Employee compensation'),
            Account(code='5310', name='Payroll Tax Expense',         account_type='Expense',
                    description='Employer payroll taxes'),
            Account(code='5400', name='Office Supplies',             account_type='Expense',
                    description='Stationery, printing, small items'),
            Account(code='5500', name='Marketing & Advertising',     account_type='Expense',
                    description='Promotion and advertising costs'),
            Account(code='5600', name='Insurance Expense',           account_type='Expense',
                    description='Business insurance premiums'),
            Account(code='5700', name='Depreciation Expense',        account_type='Expense',
                    description='Depreciation on fixed assets'),
            Account(code='5800', name='Professional Fees',           account_type='Expense',
                    description='Legal, accounting, consulting fees'),
            Account(code='5900', name='Miscellaneous Expense',       account_type='Expense',
                    description='Other operating expenses'),
        ]
        db.session.add_all(default_accounts)
        print(f"[INIT] Created {len(default_accounts)} default accounts.")

    db.session.commit()
    print("[INIT] Database initialized successfully.")


# Create the application instance
app = create_app()

if __name__ == '__main__':
    print("=" * 60)
    print("  AccounTrack – Accounting Management System")
    print("=" * 60)
    print(f"  Admin Login: admin@company.com / admin123")
    print(f"  URL: http://127.0.0.1:8080")
    print("=" * 60)
    app.run(debug=True, host='127.0.0.1', port=8080)
