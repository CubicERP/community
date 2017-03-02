# -*- coding: utf-8 -*-
from openerp import api, models, fields, _
from openerp.exceptions import except_orm
from datetime import date, timedelta


def _all_taxes(x):
    """
    Filter to select all taxes
    """
    return True


def _all_except_vat(x):
    """
    Filter to select all taxes except IVA
    """
    return x.tax_code_id.parent_id.name != 'IVA'


class account_invoice_line(models.Model):
    """
    Line of an invoice.
    Compute pirces with and without vat, for unit or line quantity.
    """
    _name = "account.invoice.line"
    _inherit = "account.invoice.line"

    @api.one
    @api.depends('quantity', 'discount', 'price_unit', 'invoice_line_tax_id',
                 'product_id', 'invoice_id.partner_id',
                 'invoice_id.currency_id')
    def compute_price(self, context=None):
        self.price_unit_vat_included = self.price_calc(use_vat=True, quantity=1)
        self.price_subtotal_vat_included = self.price_calc(use_vat=True)
        self.price_unit_not_vat_included = self.price_calc(
            use_vat=False, quantity=1)
        self.price_subtotal_not_vat_included = self.price_calc(use_vat=False)

    price_unit_vat_included = fields.Float(compute='compute_price')
    price_subtotal_vat_included = fields.Float(compute='compute_price')
    price_unit_not_vat_included = fields.Float(compute='compute_price')
    price_subtotal_not_vat_included = fields.Float(compute='compute_price')

    @api.v8
    def price_calc(self, use_vat=True, tax_filter=None, quantity=None,
                   discount=None, context=None):
        assert len(self) == 1, "Use price_calc with one instance"
        _tax_filter = tax_filter or (use_vat and _all_taxes) or _all_except_vat
        _quantity = quantity if quantity is not None else self.quantity
        _discount = discount if discount is not None else self.discount
        _price = self.price_unit * (1-(_discount or 0.0)/100.0)

        taxes = self.invoice_line_tax_id.filtered(_tax_filter).compute_all(
            _price,
            _quantity,
            product=self.product_id,
            partner=self.invoice_id.partner_id
        )
        return (self.invoice_id.currency_id.round(taxes['total_included'])
                if self.invoice_id else taxes['total_included'])

    @api.v8
    def compute_all(self, tax_filter=lambda tax: True, context=None):
        res = {}
        for line in self:
            _quantity = line.quantity
            _discount = line.discount
            _price = line.price_unit * (1-(_discount or 0.0)/100.0)
            taxes = line.invoice_line_tax_id.filtered(tax_filter).compute_all(
                _price, _quantity,
                product=line.product_id,
                partner=line.invoice_id.partner_id)

            _round = ((lambda x: line.invoice_id.currency_id.round(x))
                      if line.invoice_id else (lambda x: x))
            res[line.id] = {
                'amount_untaxed': _round(taxes['total']),
                'amount_tax': _round(taxes['total_included']) -
                _round(taxes['total']),
                'amount_total': _round(taxes['total_included']),
                'taxes': taxes['taxes'],
            }
        return res.get(len(self) == 1 and res.keys()[0], res)

account_invoice_line()


class account_invoice(models.Model):
    """
    Argentine invoice functions.
    """
    _name = "account.invoice"
    _inherit = "account.invoice"

    @api.depends('invoice_line.product_id.type')
    def _get_concept(self):
        """
        Compute concept type from selected products in invoice.
        """
        concept_obj = self.env['afip.concept_type']

        for inv in self:
            product_types = set(
                [line.product_id.type for line in inv.invoice_line])
            inv.afip_concept = concept_obj.get_code(product_types)

    def _get_service_begin_date(self):
        today = date.today()
        first = date(day=1, month=today.month, year=today.year)
        prev_last_day = first - timedelta(days=1)
        period = self.period_id.find(prev_last_day)
        return period and period.date_start or False

    def _get_service_end_date(self):
        today = date.today()
        first = date(day=1, month=today.month, year=today.year)
        prev_last_day = first - timedelta(days=1)
        period = self.period_id.find(prev_last_day)
        return period and prev_last_day or False

    def create(self, cr, uid, values, context=None):
        """
        Create a new journal. If you set 'not_auto_journal' in
        context the automatic selection of journal not work.
        """
        # Fix when create partner outside l10n_ar
        # system select a wrong journal
        if context is None:
            context = {}
        if 'not_auto_journal' not in context and \
                'journal_id' in values and \
                'partner_id' in values and \
                'type' in values:
            users_obj = self.pool.get('res.users')
            partner_obj = self.pool.get('res.partner')
            company_id = values.get(
                'company_id',
                users_obj.browse(cr, uid, uid).company_id.id)
            values['journal_id'] = (
                partner_obj.prefered_journals(
                    cr, uid,
                    values['partner_id'], company_id, values['type'],
                    context=context) + [False]
            )[0]
        return super(account_invoice, self).create(cr, uid, values,
                                                   context=context)

    afip_concept = fields.Selection([('1', 'Consumible'),
                                     ('2', 'Service'),
                                     ('3', 'Mixted')],
                                    compute="_get_concept",
                                    store=False,
                                    help="AFIP invoice concept.")
    afip_service_start = fields.Date('Service Start Date',
                                     default=_get_service_begin_date)
    afip_service_end = fields.Date('Service End Date',
                                   default=_get_service_end_date)

    @api.multi
    def action_date_assign(self):
        self.afip_validation()
        return super(account_invoice,self).action_date_assign()
    
    def afip_validation(self):
        """
        Check basic AFIP request to generate invoices.
        """
        for invoice in self:
            # If parter is not in Argentina, ignore it.
            if invoice.company_id.partner_id.country_id.name != 'Argentina':
                continue
            # Check if you choose the right journal.
            journal_class = invoice.journal_id.journal_class_id
            afip_code = journal_class.afip_code
            jou_inv = [1, 6, 11, 51, 19, 2, 7, 12, 52, 20]
            jou_ref = [3, 8, 13, 53, 21]
            if invoice.type == 'out_invoice' and afip_code not in jou_inv:
                raise except_orm(
                    _('Wrong Journal'),
                    _('Out invoice journal must have a valid journal class.'))
            if invoice.type == 'out_refund' and afip_code not in jou_ref:
                raise except_orm(
                    _('Wrong Journal'),
                    _('Out invoice journal must have a valid journal class.'))
            self.env['account.journal'].afip_partner_validation(invoice.partner_id, invoice.journal_id, invoice.amount_total, context=self._context)
        return True

    def compute_all(self, cr, uid, ids,
                    line_filter=lambda line: True,
                    tax_filter=lambda tax: True,
                    context=None):
        res = {}
        for inv in self.browse(cr, uid, ids, context=context):
            amounts = []
            for line in inv.invoice_line:
                if line_filter(line):
                    amounts.append(
                        line.compute_all(
                            tax_filter=tax_filter, context=context))

            s = {
                'amount_total': 0,
                'amount_tax': 0,
                'amount_untaxed': 0,
                'taxes': [],
            }
            for amount in amounts:
                for key, value in amount.items():
                    s[key] = s.get(key, 0) + value

            res[inv.id] = s

        return res.get(len(ids) == 1 and ids[0], res)

    @api.multi
    def onchange_partner_id(self, type, partner_id, date_invoice=False,
                            payment_term=False, partner_bank_id=False,
                            company_id=False):

        result = super(account_invoice, self).onchange_partner_id(
            type, partner_id, date_invoice, payment_term,
            partner_bank_id, company_id)

        if partner_id:
            # Set list of valid journals by partner responsability
            # partner_obj = self.pool.get('res.partner')
            partner = self.env['res.partner'].browse(partner_id)
            company = self.env['res.company'].browse(company_id)
            responsability = partner.responsability_id

            if not responsability:
                    result['warning'] = {
                        'title':
                        _('The partner has not set any fiscal responsability'),
                        'message':
                        _('Please, set partner fiscal responsability in the'
                          ' partner form before continuing.')}
                    return result

            if responsability.issuer_relation_ids is None:
                return result

            if not company.partner_id.responsability_id.id:
                result['warning'] = {
                    'title':
                    _('Your company has not set any fiscal responsability'),
                    'message':
                    _('Please, set your company responsability in the company'
                      ' form before continuing.')}
                return result

            accepted_journal_ids = partner.prefered_journals(company_id, type)
            accepted_journal_ids = [j.id for j in accepted_journal_ids]

            if 'domain' not in result:
                result['domain'] = {}
            if 'value' not in result:
                result['value'] = {}

            if accepted_journal_ids:
                result['domain'].update({
                    'journal_id': [('id', 'in', accepted_journal_ids)],
                })
                result['value'].update({
                    'journal_id': accepted_journal_ids[0],
                })
            else:
                result['domain'].update({
                    'journal_id': [('id', 'in', [])],
                })
                result['value'].update({
                    'journal_id': False,
                })

        return result