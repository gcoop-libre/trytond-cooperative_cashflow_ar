# This file is part of the cooperative_cashflow_ar module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from decimal import Decimal
from dateutil.relativedelta import relativedelta

from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateView, StateReport, Button
from trytond.report import Report
from trytond.pool import Pool
from trytond.pyson import Eval, If
from trytond.transaction import Transaction


MAX_COLS = 24


class PrintCashFlowReportStart(ModelView):
    'Print Cash-Flow'
    __name__ = 'cooperative_ar.print_cashflow.start'

    company = fields.Many2One('company.company', 'Company', required=True)
    analytic_account = fields.Many2One('analytic_account.account',
        'Analytic Account', required=True,
        domain=[
            ('company', '=', Eval('company', -1)),
            ('type', '=', 'root'),
            ],
        depends=['company'])
    from_date = fields.Date('From Date', required=True,
        domain=[
            If(Eval('to_date') & Eval('from_date'),
                ('from_date', '<=', Eval('to_date')),
                ()),
            ],
        depends=['to_date'])
    to_date = fields.Date('To Date', required=True,
        domain=[
            If(Eval('from_date') & Eval('to_date'),
                ('to_date', '>=', Eval('from_date')),
                ()),
            ],
        depends=['from_date'])

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company')


class PrintCashFlowReport(Wizard):
    'Print Cash-Flow'
    __name__ = 'cooperative_ar.print_cashflow'

    start = StateView('cooperative_ar.print_cashflow.start',
        'cooperative_cashflow_ar.print_cashflow_report_start_view', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-print', True),
            ])
    print_ = StateReport('cooperative_ar.cashflow')

    def do_print_(self, action):
        data = {
            'company': self.start.company.id,
            'analytic_account': self.start.analytic_account.id,
            'from_date': self.start.from_date,
            'to_date': self.start.to_date,
            }
        return action, data


class CashFlowReport(Report):
    'Cash-Flow'
    __name__ = 'cooperative_ar.cashflow'

    @classmethod
    def get_context(cls, records, header, data):
        pool = Pool()
        Company = pool.get('company.company')

        report_context = super().get_context(records, header, data)

        report_context['company'] = Company(data['company'])
        report_context['from_date'] = data['from_date']
        report_context['to_date'] = data['to_date']

        columns = cls._get_date_columns(data['from_date'], data['to_date'])
        report_context['columns'] = [x['lbl']
            for x in columns.values()] + ['Total']
        if len(report_context['columns']) < MAX_COLS:
            for idx in range(MAX_COLS - len(report_context['columns'])):
                report_context['columns'].append('')

        # Sales
        sales_raw = cls._get_sale_records(data)
        report_context['sales_raw'] = sales_raw.values()

        sales_summary = cls._get_sale_summary(columns, sales_raw)
        report_context['sales_summary'] = sales_summary.values()

        # Expenses
        expenses_raw = cls._get_expense_records(data)
        report_context['expenses_raw'] = expenses_raw.values()

        expenses_summary = cls._get_expense_summary(columns, expenses_raw)
        report_context['expenses_summary'] = expenses_summary.values()

        # Cooperative Receipts
        receipts_raw = cls._get_receipt_records(data)
        report_context['receipts_raw'] = receipts_raw.values()

        receipts_summary = cls._get_receipt_summary(columns, receipts_raw)
        report_context['receipts_summary'] = receipts_summary.values()

        # Synthesis
        synthesis = cls._get_synthesis(columns,
            sales_summary, expenses_summary, receipts_summary)
        report_context['synthesis'] = synthesis.values()

        return report_context

    @classmethod
    def _get_date_columns(cls, from_date, to_date):
        res = {}
        date = from_date
        idx = 0
        while date < to_date and idx < MAX_COLS:
            year, month = date.year, date.month
            res[(year, month)] = {'idx': idx, 'lbl': '%s/%s' % (month, year)}
            date = date + relativedelta(months=1)
            idx += 1
        return res

    @classmethod
    def _get_sale_records(cls, data):
        pool = Pool()
        Company = pool.get('company.company')
        Currency = pool.get('currency.currency')
        SaleLine = pool.get('sale.line')
        AnalyticAccount = pool.get('analytic_account.account')

        records = {}
        company = Company(data['company'])

        clause = [
            ('sale.company', '=', data['company']),
            ('sale.state', 'in',
                ['projected', 'confirmed', 'processing', 'done']),
            ('type', '=', 'line'),
            ('manual_delivery_date', '>=', data['from_date']),
            ('manual_delivery_date', '<=', data['to_date']),
            ]
        sale_lines = SaleLine.search(clause,
            order=[('manual_delivery_date', 'ASC')])
        if not sale_lines:
            return records

        for line in sale_lines:
            year = line.manual_delivery_date.year
            month = line.manual_delivery_date.month
            category_id = None
            for analytic_line in line.analytic_accounts:
                if (analytic_line.root.id == data['analytic_account'] and
                        analytic_line.account):
                    category_id = analytic_line.account.id
            key = (year, month, category_id)
            if key not in records:
                records[key] = {
                    'year': year,
                    'month': month,
                    'category': (category_id and
                        AnalyticAccount(category_id).name or ''),
                    'amount': Decimal(0),
                    }
            with Transaction().set_context(date=line.manual_delivery_date):
                records[key]['amount'] += Currency.compute(
                    company.currency, line.amount, line.currency)
        return records

    @classmethod
    def _get_sale_summary(cls, columns, sales_raw):
        records = {}
        for key, line in sales_raw.items():
            category_id = key[2]
            if category_id not in records:
                records[category_id] = {
                    'category': line['category'],
                    'columns': dict((idx, None) for idx in range(MAX_COLS)),
                    'total': Decimal(0),
                    }
            date = key[:2]
            if date not in columns:
                continue
            records[category_id]['columns'][columns[date]['idx']] = line[
                'amount']
            records[category_id]['total'] += line['amount']

        total_idx = len(columns)
        for k, v in records.items():
            v['columns'][total_idx] = v['total']
        return records

    @classmethod
    def _get_purchase_records(cls):
        return []

    @classmethod
    def _get_expense_records(cls, data):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        AnalyticAccount = pool.get('analytic_account.account')

        records = {}

        clause = [
            ('move.company', '=', data['company']),
            ('account.cashflow_report', '=', True),
            ('move.state', '=', 'posted'),
            ('move.date', '>=', data['from_date']),
            ('move.date', '<=', data['to_date']),
            ]
        move_lines = MoveLine.search(clause,
            order=[('move.date', 'ASC')])
        if not move_lines:
            return records

        for line in move_lines:
            year = line.move.date.year
            month = line.move.date.month
            category_id = None
            for analytic_line in line.analytic_lines:
                if (analytic_line.account.root.id ==
                        data['analytic_account'] and
                        analytic_line.account):
                    category_id = analytic_line.account.id
            key = (year, month, category_id)
            if key not in records:
                records[key] = {
                    'year': year,
                    'month': month,
                    'category': (category_id and
                        AnalyticAccount(category_id).name or ''),
                    'amount': Decimal(0),
                    }
            with Transaction().set_context(date=line.move.date):
                records[key]['amount'] += abs(line.debit - line.credit)
        return records

    @classmethod
    def _get_expense_summary(cls, columns, expenses_raw):
        records = {}
        for key, line in expenses_raw.items():
            category_id = key[2]
            if category_id not in records:
                records[category_id] = {
                    'category': line['category'],
                    'columns': dict((idx, None) for idx in range(MAX_COLS)),
                    'total': Decimal(0),
                    }
            date = key[:2]
            if date not in columns:
                continue
            records[category_id]['columns'][columns[date]['idx']] = line[
                'amount']
            records[category_id]['total'] += line['amount']

        total_idx = len(columns)
        for k, v in records.items():
            v['columns'][total_idx] = v['total']
        return records

    @classmethod
    def _get_receipt_records(cls, data):
        pool = Pool()
        Company = pool.get('company.company')
        Currency = pool.get('currency.currency')
        Recibo = pool.get('cooperative.partner.recibo')
        AnalyticAccount = pool.get('analytic_account.account')

        records = {}
        company = Company(data['company'])

        clause = [
            ('company', '=', data['company']),
            ('state', 'in', ['projected', 'confirmed']),
            ('date', '>=', data['from_date']),
            ('date', '<=', data['to_date']),
            ]
        receipts = Recibo.search(clause,
            order=[('date', 'ASC')])
        if not receipts:
            return records

        for line in receipts:
            year = line.date.year
            month = line.date.month
            category_id = None
            #for analytic_line in line.analytic_accounts:
                #if (analytic_line.root.id == data['analytic_account'] and
                        #analytic_line.account):
                    #category_id = analytic_line.account.id
            key = (year, month, line.partner.id, category_id)
            if key not in records:
                records[key] = {
                    'year': year,
                    'month': month,
                    'partner': line.partner.rec_name,
                    'category': (category_id and
                        AnalyticAccount(category_id).name or ''),
                    'amount': Decimal(0),
                    }
            with Transaction().set_context(date=line.date):
                records[key]['amount'] += Currency.compute(
                    company.currency, line.amount, line.currency)
        return records

    @classmethod
    def _get_receipt_summary(cls, columns, receipts_raw):
        records = {}
        for key, line in receipts_raw.items():
            partner_id = key[2]
            if partner_id not in records:
                records[partner_id] = {
                    'partner': line['partner'],
                    'columns': dict((idx, None) for idx in range(MAX_COLS)),
                    'total': Decimal(0),
                    }
            date = key[:2]
            if date not in columns:
                continue
            records[partner_id]['columns'][columns[date]['idx']] = line[
                'amount']
            records[partner_id]['total'] += line['amount']

        total_idx = len(columns)
        for k, v in records.items():
            v['columns'][total_idx] = v['total']
        return records

    @classmethod
    def _get_synthesis(cls, columns,
            sales_summary, expenses_summary, receipts_summary):
        records = {}
        result_columns = dict((idx, None) for idx in range(MAX_COLS))

        # Sales
        records[1] = {
            'name': 'Ventas',
            'columns': dict((idx, None) for idx in range(MAX_COLS)),
            }
        for record in sales_summary.values():
            for idx, value in record['columns'].items():
                if value is None:
                    continue
                if records[1]['columns'][idx] is None:
                    records[1]['columns'][idx] = Decimal(0)
                records[1]['columns'][idx] += value
                if result_columns[idx] is None:
                    result_columns[idx] = Decimal(0)
                result_columns[idx] += value

        # Expenses
        records[2] = {
            'name': 'Gastos',
            'columns': dict((idx, None) for idx in range(MAX_COLS)),
            }
        for record in expenses_summary.values():
            for idx, value in record['columns'].items():
                if value is None:
                    continue
                if records[2]['columns'][idx] is None:
                    records[2]['columns'][idx] = Decimal(0)
                records[2]['columns'][idx] += value
                if result_columns[idx] is None:
                    result_columns[idx] = Decimal(0)
                result_columns[idx] -= value

        # Cooperative Receipts
        records[3] = {
            'name': 'Retiros',
            'columns': dict((idx, None) for idx in range(MAX_COLS)),
            }
        for record in receipts_summary.values():
            for idx, value in record['columns'].items():
                if value is None:
                    continue
                if records[3]['columns'][idx] is None:
                    records[3]['columns'][idx] = Decimal(0)
                records[3]['columns'][idx] += value
                if result_columns[idx] is None:
                    result_columns[idx] = Decimal(0)
                result_columns[idx] -= value

        # Result
        records[9] = {
            'name': 'Resultado',
            'columns': result_columns,
            }

        return records
