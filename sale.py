# This file is part of the cooperative_cashflow_ar module for Tryton.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from decimal import Decimal
from simpleeval import simple_eval

from trytond.model import Workflow, ModelView, fields
from trytond.model.exceptions import ValidationError
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.i18n import gettext
from trytond.tools import decistmt
from trytond.modules.product import round_price


class Sale(metaclass=PoolMeta):
    __name__ = 'sale.sale'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        state = ('projected', 'Projected')
        if state not in cls.state.selection:
            cls.state.selection.append(state)
        cls._transitions |= set((
            ('draft', 'projected'),
            ('projected', 'draft'),
            ))
        cls._buttons['draft']['invisible'] = ~Eval('state').in_(
            ['projected', 'cancelled', 'quotation', 'confirmed'])
        cls._buttons.update({
            'project': {
                'invisible': Eval('state') != 'draft',
                'depends': ['state'],
                },
            })

    @classmethod
    @ModelView.button
    @Workflow.transition('projected')
    def project(cls, sales):
        pass


class UpdateSaleProjectionStart(ModelView):
    'Update Sale Projection'
    __name__ = 'sale.update_projection.start'

    from_date = fields.Date('From Date', required=True,
        help='Delivery Date from which the prices will be updated')
    formula = fields.Char('Unit Price Formula', required=True,
        help=('Python expression that will be evaluated with:\n'
            '- unit_price: the current unit price of each line'))

    @classmethod
    def default_from_date(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today()

    @classmethod
    def default_formula(cls):
        return 'unit_price'


class UpdateSaleProjection(Wizard):
    'Update Sale Projection'
    __name__ = 'sale.update_projection'

    start_state = 'check'
    check = StateTransition()
    start = StateView('sale.update_projection.start',
        'cooperative_cashflow_ar.sale_update_projection_start_view', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Update', 'update', 'tryton-ok', True),
            ])
    update = StateTransition()

    def transition_check(self):
        sale = self.record
        if sale.state == 'projected':
            return 'start'
        return 'end'

    def transition_update(self):
        self.check_formula()
        self.update_unit_price()
        return 'end'

    def check_formula(self):
        try:
            if not isinstance(self.get_unit_price(Decimal(0)), Decimal):
                raise ValueError
        except Exception as exception:
            raise ValidationError(gettext(
                'cooperative_cashflow_ar.msg_invalid_formula',
                formula=self.start.formula,
                exception=exception)) from exception

    def get_unit_price(self, unit_price, **context):
        context.setdefault('names', {})['unit_price'] = unit_price
        context.setdefault('functions', {})['Decimal'] = Decimal
        return simple_eval(decistmt(self.start.formula), **context)

    def update_unit_price(self):
        pool = Pool()
        SaleLine = pool.get('sale.line')

        for sale in self.records:
            if sale.state != 'projected':
                continue
            sale_lines = []
            for line in sale.lines:
                if line.type != 'line':
                    continue
                if (not line.manual_delivery_date or
                        self.start.from_date > line.manual_delivery_date):
                    continue
                unit_price = round_price(self.get_unit_price(line.unit_price))
                line.unit_price = unit_price
                line.amount = line.on_change_with_amount()
                sale_lines.append(line)
            if sale_lines:
                SaleLine.save(sale_lines)
