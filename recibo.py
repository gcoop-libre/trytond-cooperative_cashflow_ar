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


class Recibo(metaclass=PoolMeta):
    __name__ = 'cooperative.partner.recibo'

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
            ['projected', 'cancelled'])
        cls._buttons.update({
            'project': {
                'invisible': Eval('state') != 'draft',
                'depends': ['state'],
                },
            })

    @classmethod
    @ModelView.button
    @Workflow.transition('projected')
    def project(cls, recibos):
        pass


class ReciboLote(metaclass=PoolMeta):
    __name__ = 'cooperative.partner.recibo.lote'

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
            ['projected', 'cancelled'])
        cls._buttons.update({
            'project': {
                'invisible': Eval('state') != 'draft',
                'depends': ['state'],
                },
            })

    @classmethod
    @ModelView.button
    @Workflow.transition('projected')
    def project(cls, lotes):
        pool = Pool()
        Recibo = pool.get('cooperative.partner.recibo')
        for lote in lotes:
            Recibo.project(lote.recibos)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, lotes):
        pool = Pool()
        Recibo = pool.get('cooperative.partner.recibo')
        super().draft(lotes)
        for lote in lotes:
            Recibo.draft(lote.recibos)


class UpdateReciboLoteProjectionStart(ModelView):
    'Update Recibo Projection'
    __name__ = 'cooperative.lote.update_projection.start'

    formula = fields.Char('Unit Price Formula', required=True,
        help=('Python expression that will be evaluated with:\n'
            '- amount: the current amount of each receipt'))

    @classmethod
    def default_formula(cls):
        return 'amount'


class UpdateReciboLoteProjection(Wizard):
    'Update Recibo Projection'
    __name__ = 'cooperative.lote.update_projection'

    start_state = 'check'
    check = StateTransition()
    start = StateView('cooperative.lote.update_projection.start',
        'cooperative_cashflow_ar.lote_update_projection_start_view', [
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
        self.update_amount()
        return 'end'

    def check_formula(self):
        try:
            if not isinstance(self.get_amount(Decimal(0)), Decimal):
                raise ValueError
        except Exception as exception:
            raise ValidationError(gettext(
                'cooperative_cashflow_ar.msg_invalid_formula',
                formula=self.start.formula,
                exception=exception)) from exception

    def get_amount(self, amount, **context):
        context.setdefault('names', {})['amount'] = amount
        context.setdefault('functions', {})['Decimal'] = Decimal
        return simple_eval(decistmt(self.start.formula), **context)

    def update_amount(self):
        pool = Pool()
        Recibo = pool.get('cooperative.partner.recibo')

        for lote in self.records:
            if lote.state != 'projected':
                continue
            recibos = []
            for recibo in lote.recibos:
                if recibo.state != 'projected':
                    continue
                amount = self.get_amount(recibo.amount).quantize(
                    Decimal(1) / 10 ** 2)
                recibo.amount = amount
                recibos.append(recibo)
            if recibos:
                Recibo.save(recibos)
