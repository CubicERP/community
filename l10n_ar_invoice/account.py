# -*- coding: utf-8 -*-
from openerp.osv import fields, osv
from openerp.tools.translate import _


class account_journal(osv.osv):
    _inherit = "account.journal"
    _columns = {
        'code': fields.char('Code', size=10, required=True,
                            help="The code will be used to generate the numbers"
                            "of the journal entries of this journal."),
        'journal_class_id': fields.many2one('afip.journal_class',
                                            'Document class'),
        'point_of_sale': fields.integer('Point of sale ID'),
        'priority': fields.integer('Priority select ordering'),
    }

    _order = 'priority'
    
    def afip_partner_validation(self, cr, uid, partner_id, journal_id, amount_total, context=None):
        # Partner responsability ?
        if not partner_id.responsability_id:
            raise osv.except_orm(
                _('No responsability'),
                _('Your partner have not afip responsability assigned.'
                  ' Assign one please.'))

        # Take responsability classes for this journal
        invoice_class = journal_id.journal_class_id.document_class_id
        my_company = journal_id.company_id
        resp_class = self.pool['afip.responsability_relation'].search(cr, uid, [
            ('document_class_id', '=', invoice_class.id),
            ('issuer_id.code', '=', my_company.partner_id.responsability_id.code)], context=context)

        # You can emmit this document?
        if not resp_class:
            raise osv.except_orm(
                _('Invalid emisor'),
                _('Your responsability with AFIP dont let you generate'
                  ' this kind of document.'))

        # Partner can receive this document?
        resp_class = self.pool['afip.responsability_relation'].search(cr, uid, [
            ('document_class_id', '=', invoice_class.id),
            ('receptor_id.code', '=', partner_id.responsability_id.code)], context=context)
        if not resp_class:
            raise osv.except_orm(
                _('Invalid receptor'),
                _('Your partner cant receive this document.'
                  ' Check AFIP responsability of the partner,'
                  ' or Journal Account of the invoice.'))

        # If Final Consumer have pay more than 1000$,
        # you need more information to generate document.
        if partner_id.responsability_id.code == 'CF' \
                and amount_total > 1000 and \
                (partner_id.document_type_id.code in [None, 'Sigd']
                 or partner_id.document_number is None):
            raise osv.except_orm(
                _('Partner without Identification'),
                _('Total > $1000.- need partner identification.'))
        return True


class res_currency(osv.osv):
    _inherit = "res.currency"
    _columns = {
        'afip_code': fields.char('AFIP Code', size=4),
    }