# -*- coding: utf-8 -*-
# TODO: vat_rate
from openerp.osv import fields, osv
from openerp.tools.translate import _
from openerp.addons.l10n_ar_fpoc.invoice import \
    document_type_map, responsability_map


class pos_config(osv.osv):
    _name = 'pos.config'
    _inherit = 'pos.config'
    

    _columns = {
        'fpoc_close_report': fields.selection(
            [('z_report', 'Z Report'), ('x_report', 'X Report')],
            "Report to Generate at Close"
        ),
        'afip_journal_b_id': fields.many2one('account.journal', string='AFIP Journal B', help="Select the journal for invoices type B"),
    }


class pos_session(osv.osv):
    _name = 'pos.session'
    _inherit = 'pos.session'

#     def wkf_action_open(self, cr, uid, ids, context=None):
#         r = super(pos_session, self).wkf_action_open(
#             cr, uid, ids, context=context)
#         # Apertura de caja.
#         for sess in [s for s in self.browse(cr, uid, ids)
#                      if s.config_id.journal_id.use_fiscal_printer and
#                      s.config_id.journal_id.fiscal_printer_id]:
#             jou = sess.config_id.journal_id
#             if jou.fiscal_printer_state not in ['ready']:
#                 jou.open_fiscal_journal()
#  
#         return r

    def wkf_action_close(self, cr, uid, ids, context=None):
        r = super(pos_session, self).wkf_action_close(
            cr, uid, ids, context=context)
        # Cierre de caja, Informe Z o X
        for sess in [s for s in self.browse(cr, uid, ids)
                     if s.config_id.journal_id.use_fiscal_printer and
                     s.config_id.journal_id.fiscal_printer_id]:
            if sess.config_id.fpoc_close_report == 'z_report':
                sess.config_id.journal_id.close_fiscal_journal()
            elif sess.config_id.fpoc_close_report == 'x_report':
                sess.config_id.journal_id.shift_change()
            pass
        return r


class pos_order(osv.osv):
    _name = "pos.order"
    _inherit = "pos.order"

    _columns = {
            'origin_id': fields.many2one('pos.order', 'POS Order Origin', states={'draft': [('readonly', False)]}, readonly=True),
            'afip_printed': fields.boolean('AFIP Printed', states={'draft': [('readonly', False)]}, readonly=True, 
                                           help="This POS Order was printed through AFIP fiscal printer", copy=False),
        }
    
    def _get_sale_journal(self, cr, uid, order, context=None):
        res = super(pos_order, self)._get_sale_journal(cr, uid, order, context=context)
        if order.sale_journal.id == res.id and order.partner_id.responsability_id.code != 'IVARI':
            res = order.session_id.config_id.afip_journal_b_id or order.sale_journal
        if order.amount_total < 0:
            res = res.reverse_journal_id or res
        return res

    def number(self, cr, uid, ids, context=None):
        for order in self.browse(cr, uid, ids, context=context):
            sale_journal = self._get_sale_journal(cr, uid, order, context=context)
            if order.name == '/' and sale_journal.use_fiscal_printer  and not order.afip_printed:
                self.print_pos_ticket(cr, uid, order, sale_journal, context=context)
                self.write(cr, uid, [order.id], {'name': sale_journal.sequence_id._next()}, context=context) 
        return super(pos_order, self).number(cr, uid, ids, context=context)
    
    def _get_invoice_create(self, cr, uid, order, context=None):
        res = super(pos_order,self)._get_invoice_create(cr, uid, order, context=context)
        res['afip_printed'] = order.afip_printed
        return res
    
    def _get_refund_clone_order(self, order, current_session_ids, context=None):
        res = super(pos_order,self)._get_refund_clone_order(order, current_session_ids, context=context)
        res['origin_id'] = order.id
        return res
    
    def print_pos_ticket(self, cr, uid, order, journal, context=None):
        #self._check_printer(journal)
        if (abs(order.amount_total) > 25000):
            raise osv.except_osv(_('Error!'),
                                 _("Total must less than 25000 $"))
        partner = order.partner_id or order.sale_journal.fiscal_printer_anon_partner_id or False
        if not partner:
            raise osv.except_osv(_('Partner Error'),_('You must select a anonymous partner in the journal %s')%order.sale_journal.name)
        self.pool['account.journal'].afip_partner_validation(cr, uid, partner, journal, abs(order.amount_total), context=context)
        # If amount is negative is a credit note else an invoice.
        if order.amount_total < 0:
            ticket = self.build_ticket_notacredito(cr, uid, order, context=context)
            r = journal.make_ticket_notacredito(ticket)[journal.id]
        else:
            ticket = self.build_ticket_factura(cr, uid, order, context=context)
            r = journal.make_ticket_factura(ticket)[journal.id]
        # Verifing if the ticket was cancelled
        ticket_canceled = r and r.get('error', 'x') == 'ticket canceled'
        if r and 'error' in r and not ticket_canceled:
            # Raise if an error and not cancelation happen
            raise osv.except_osv(
                _('Printer Error!'),
                _('Printer return: %s') % r['error'])
        if 'document_type' not in r or 'document_number' not in r:
            raise osv.except_osv(
                _('Printer Error!'),
                _('No number was assigned!'))

        # Generate ticket number
        document_type = r['document_type']
        document_number = int(r['document_number'])
        
        
        if document_type <> journal.journal_class_id.document_class_id.name:
            raise osv.except_osv(
                _('Journal Document Class Error'),
                _('The document class associated to the invoice journal must be %s, check please !')%document_type)
        
        # If ticket was canceled
        if r.get('command', '') == 'cancel_ticket_factura':
            raise osv.except_osv(
                _('User Error'),
                _('The printer work has been cancelled, you must cancel this invoice manually !'))
        
        if journal.sequence_id.number_next_actual != document_number:
            self.pool.get('ir.sequence').write(cr, uid, [journal.sequence_id.id], {'number_next_actual': document_number}, context=context)
        self.write(cr, uid, [order.id], {'afip_printed': True}, context=context)
        return document_type, document_number
    
    def build_ticket_factura(self, cr, uid, order, context=None):
        o = order
        ticket = {
            "ticket_id": "pos.order,%s"%o.id,
            "turist_ticket": False,
            "debit_note": False,
            "partner": {
                "name": o.partner_id.name or "",
                "name_2": "",
                "address": o.partner_id.street or "",
                "address_2": o.partner_id.city or "",
                "address_3": o.partner_id.country_id.name or "",
                "document_type": document_type_map.get(
                    o.partner_id.document_type_id.code, "D"),
                "document_number": o.partner_id.document_number,
                "responsability": responsability_map.get(
                    o.partner_id.responsability_id.code, "F"),
            },
            "related_document": o.picking_id and o.picking_id.name
            or _("No picking"),
            "related_document_2": o.picking_id and o.picking_type_id
            and o.picking_type_id.name or "",
            "turist_check": "",
            "lines": [],
            "payments": [],
            "cut_paper": True,
            "electronic_answer": False,
            "print_return_attribute": False,
            "current_account_automatic_pay": False,
            "print_quantities": True,
            "tail_no": 1 if o.user_id.name else 0,
            "tail_text": _("Saleman: %s") % o.user_id.name
            if o.user_id.name else "",
            "tail_no_2": 0,
            "tail_text_2": "",
            "tail_no_3": 0,
            "tail_text_3": "",
        }
        for line in o.lines:
            vat_rate = ([t.amount
                         for t in line.product_id.product_tmpl_id.taxes_id
                         if 'IVA' in t.ref_tax_code_id.name] + [0])[0] * 100
            ticket["lines"].append({
                "item_action": "sale_item",
                "as_gross": False,
                "send_subtotal": True,
                "check_item": False,
                "collect_type": "q",
                "large_label": "",
                "first_line_label": "",
                "description": "[%s]" % (line.product_id.ean13 or 0),
                "description_2": "",
                "description_3": "",
                "description_4": "",
                "item_description": line.product_id.name,
                "quantity": line.qty,
                "unit_price": line.price_unit,
                "vat_rate": vat_rate,
                "fixed_taxes": 0,
                "taxes_rate": 0
            })
            if line.discount > 0:
                ticket["lines"].append({
                    "item_action": "discount_item",
                    "as_gross": False,
                    "send_subtotal": True,
                    "check_item": False,
                    "collect_type": "q",
                    "large_label": "",
                    "first_line_label": "",
                    "description": "",
                    "description_2": "",
                    "description_3": "",
                    "description_4": "",
                    "item_description": "%5.2f%%" % line.discount,
                    "quantity": line.qty,
                    "unit_price": line.price_unit * (
                        line.discount/100.),
                    "vat_rate": vat_rate,
                    "fixed_taxes": 0,
                    "taxes_rate": 0
                })
        for st in o.statement_ids:
            ticket["payments"].append({
                "null_pay": (o.amount_total < 0),
                "include_in_arching": False,
                "card_pay": False,
                "description": st.journal_id.name,
                "extra_description": False,
                "amount": st.amount,
            })
        return ticket

    def build_ticket_notacredito(self, cr, uid, order, context=None):
        o = order
        ticket = {
            "turist_ticket": False,
            "debit_note": False,
            "partner": {
                "name": o.partner_id.name or "Consumidor Final",
                "name_2": "",
                "address": o.partner_id.street or "Consumidor Final",
                "address_2": o.partner_id.city or "",
                "address_3": o.partner_id.country_id.name or "",
                "document_type": document_type_map.get(
                    o.partner_id.document_type_id.code, "D"),
                "document_number": o.partner_id.document_number or "0",
                "responsability": responsability_map.get(
                    o.partner_id.responsability_id.code, "F"),
            },
            "related_document": o.picking_id and o.picking_id.name or _("No picking"),
            "related_document_2": o.picking_id and o.picking_type_id and o.picking_type_id.name or "",
            "origin_document": o.origin_id.name if o.origin_id else _("Unknown"),
            "lines": [],
            "payments": [],
            "cut_paper": True,
            "electronic_answer": False,
            "print_return_attribute": False,
            "current_account_automatic_pay": False,
            "print_quantities": True,
            "tail_no": 1 if o.user_id.name else 0,
            "tail_text": _("Saleman: %s") % o.user_id.name
            if o.user_id.name else "",
            "tail_no_2": 0,
            "tail_text_2": "",
            "tail_no_3": 0,
            "tail_text_3": "",
            "sign_no": 3,
        }
        for line in o.lines:
            vat_rate = ([t.amount
                         for t in line.product_id.product_tmpl_id.taxes_id
                         if 'IVA' in t.ref_tax_code_id.name] + [0])[0] * 100
            ticket["lines"].append({
                "item_action": "sale_item",
                "as_gross": False,
                "send_subtotal": True,
                "check_item": False,
                "collect_type": "q",
                "large_label": "",
                "first_line_label": "",
                "description": "[%s]" % (line.product_id.ean13 or 0),
                "description_2": "",
                "description_3": "",
                "description_4": "",
                "item_description": line.product_id.name,
                "quantity": -line.qty,
                "unit_price": line.price_unit,
                "vat_rate": vat_rate,
                "fixed_taxes": 0,
                "taxes_rate": 0
            })
            if line.discount > 0:
                ticket["lines"].append({
                    "item_action": "discount_item",
                    "as_gross": False,
                    "send_subtotal": True,
                    "check_item": False,
                    "collect_type": "q",
                    "large_label": "",
                    "first_line_label": "",
                    "description": "",
                    "description_2": "",
                    "description_3": "",
                    "description_4": "",
                    "item_description": "%5.2f%%" % line.discount,
                    "quantity": -line.qty,
                    "unit_price": line.price_unit * (
                        line.discount/100.),
                    "vat_rate": vat_rate,
                    "fixed_taxes": 0,
                    "taxes_rate": 0
                })
        for st in o.statement_ids:
            ticket["payments"].append({
                "null_pay": False,
                "include_in_arching": False,
                "card_pay": False,
                "description": st.journal_id.name,
                "extra_description": False,
                "amount": -st.amount,
            })
        return ticket
    
    def _check_printer(self, journal):
        if not journal.use_fiscal_printer:
            return False

        if not journal.fiscal_printer_id:
            raise osv.except_osv(
                _('Error'),
                _('You must set a fiscal printer for the journal'))

        if journal.fiscal_printer_state not in ['ready']:
            raise osv.except_osv(
                _('Error!'),
                _('Printer is not ready to print.'))

        if journal.fiscal_printer_fiscal_state not in ['open']:
            raise osv.except_osv(
                _('Error!'),
                _('You can\'t print in a closed printer.'))

        if journal.fiscal_printer_paper_state not in ['ok']:
            raise osv.except_osv(
                _('Error!'),
                _('You can\'t print in low level of paper printer.'))

        if not journal.fiscal_printer_anon_partner_id:
            raise osv.except_osv(
                _('Error'),
                _('You must set anonymous partner to the journal.'))

        return True