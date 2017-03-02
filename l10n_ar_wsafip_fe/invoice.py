# -*- coding: utf-8 -*-
from openerp.osv import fields, osv
from openerp import registry
from openerp.tools.translate import _
import re
import logging

_logger = logging.getLogger(__name__)

# Label filter to recover invoice number
re_label = re.compile(r'%\([^\)]+\)s')


def _get_parents(child, parents=[]):
    "Functions to list parents names."
    if child:
        return parents + [child.name] + _get_parents(child.parent_id)
    else:
        return parents


class invoice(osv.osv):
    _inherit = "account.invoice"
    _columns = {
        'afip_result': fields.selection([
            ('', 'No CAE'),
            ('A', 'Accepted'),
            ('R', 'Rejected'),
        ], 'Status', help='This state is asigned by the AFIP. '
            'If * No CAE * state mean you have no generate this invoice by '),
        'afip_batch_number': fields.integer('Batch Number', readonly=True),
        'afip_cae': fields.char('CAE number', size=24),
        'afip_cae_due': fields.date('CAE due'),
        'afip_error_id': fields.many2one('afip.wsfe_error', 'AFIP Status',
                                         readonly=True),
    }

    _defaults = {
        'afip_result': '',
    }

    def valid_batch(self, cr, uid, ids, *args):
        """
        Increment batch number groupping by afip connection server.
        """
        seq_obj = self.pool.get('ir.sequence')

        conns = []
        invoices = {}
        for inv in self.browse(cr, uid, ids):
            conn = inv.journal_id.afip_connection_id
            if conn:
                diff = inv.journal_id.sequence_id.number_next - inv.journal_id.afip_items_generated
                if not (diff == 1 or diff == 2):
                    raise osv.except_osv(
                        _(u'Syncronization Error in Journal %s') %
                        (inv.journal_id.name),
                        _(u'La AFIP espera que el próximo número de secuencia sea '
                        u'%i, pero el sistema indica que será %i. '
                        u'Hable inmediatamente con su administrador del '
                        u'sistema para resolver este problema.') %
                        (inv.journal_id.afip_items_generated + 1,
                        inv.journal_id.sequence_id.number_next))
                conns.append(conn)
                invoices[conn.id] = invoices.get(conn.id, []) + [inv.id]

        for conn in conns:
            prefix = conn.batch_sequence_id.prefix or ''
            suffix = conn.batch_sequence_id.suffix or ''
            sid_re = re.compile('%s(\d*)%s' % (prefix, suffix))
            sid = seq_obj.next_by_id(cr, uid, conn.batch_sequence_id.id)
            self.write(cr, uid, invoices[conn.id], {
                'afip_batch_number': int(sid_re.search(sid).group(1)),
            })

        return True

    def get_related_invoices(self, cr, uid, ids, *args):
        """
        List related invoice information to fill CbtesAsoc
        """
        r = {}
        _ids = [ids] if isinstance(ids, int) else ids

        for inv in self.browse(cr, uid, _ids):
            r[inv.id] = []
            rel_inv_ids = self.search(cr, uid, [
                ('number', '=', inv.origin),
                ('state', 'not in', ['draft',
                                     'proforma',
                                     'proforma2',
                                     'cancel'])])
            for rel_inv in self.browse(cr, uid, rel_inv_ids):
                journal = rel_inv.journal_id
                r[inv.id].append({
                    'Tipo': journal.journal_class_id.afip_code,
                    'PtoVta': journal.point_of_sale,
                    'Nro': rel_inv.invoice_number,
                })

        return r[ids] if isinstance(ids, int) else r

    def get_taxes(self, cr, uid, ids, *args):
        r = {}
        _ids = [ids] if isinstance(ids, int) else ids

        for inv in self.browse(cr, uid, _ids):
            r[inv.id] = []

            for tax in inv.tax_line:
                if 'IVA' in _get_parents(tax.tax_code_id):
                    continue
                if tax.tax_code_id:
                    r[inv.id].append({
                        'Id': tax.tax_code_id.parent_afip_code,
                        'Desc': tax.tax_code_id.name,
                        'BaseImp': tax.base_amount,
                        'Alic': tax.tax_amount / tax.base_amount,
                        'Importe': tax.tax_amount,
                    })
                else:
                    raise osv.except_osv(
                        _(u'TAX without tax-code'),
                        _(u'Please, check if you set tax code for '
                          u'invoice or refund to tax %s.') % tax.name)

        return r[ids] if isinstance(ids, int) else r

    def get_vat(self, cr, uid, ids, *args):
        r = {}
        _ids = [ids] if isinstance(ids, int) else ids

        for inv in self.browse(cr, uid, _ids):
            r[inv.id] = []

            for tax in inv.tax_line:
                if 'IVA' not in _get_parents(tax.tax_code_id):
                    continue
                r[inv.id].append({
                    'Id': tax.tax_code_id.parent_afip_code,
                    'BaseImp': tax.base_amount,
                    'Importe': tax.tax_amount,
                })

        return r[ids] if isinstance(ids, (long, int)) else r

    def get_optionals(self, cr, uid, ids, *args):
        opt_type_obj = self.pool.get('afip.optional_type')

        r = {}
        _ids = [ids] if isinstance(ids, int) else ids
        opt_type_ids = opt_type_obj.search(cr, uid, [])

        for inv in self.browse(cr, uid, _ids):
            r[inv.id] = []
            for opt_type in opt_type_obj.browse(cr, uid, opt_type_ids):
                if opt_type.apply_rule and opt_type.value_computation:
                    """
                    Debería evaluar apply_rule para saber si esta opción se
                    computa para esta factura. Y si se computa, se evalua
                    value_computation sobre la factura y se obtiene el valor
                    que le corresponda.  Luego se debe agregar al output r.
                    """
                    raise NotImplemented

        return r[ids] if isinstance(ids, int) else r

    def action_retrieve_cae(self, cr, uid, ids, context=None):
        """
        Contact to the AFIP to get a CAE number.
        """
        if context is None:
            context = {}
        # TODO: not correct fix but required a frech values before reading it.
        self.write(cr, uid, ids, {})

        Servers = {}
        Requests = {}
        Inv2id = {}
        Inv2number = {}

        for inv in self.browse(cr, uid, ids, context=context):
            journal = inv.journal_id
            conn = journal.afip_connection_id

            # Ignore journals with cae
            if inv.afip_cae and inv.afip_cae_due:
                continue

            # Only process if set to connect to afip
            if not conn:
                continue

            # Ignore invoice if connection server is not type WSFE.
            if conn.server_id.code != 'wsfe':
                continue

            Servers[conn.id] = conn.server_id.id

            # Take the last number of the "number".
            prefix_re = ".*".join([
                re.escape(w)
                for w in re_label.split(inv.journal_id.sequence_id.prefix or "")
            ])
            suffix_re = ".*".join([
                re.escape(w)
                for w in re_label.split(inv.journal_id.sequence_id.suffix or "")
            ])
            re_number = re.compile(prefix_re + r"(\d+)" + suffix_re)
            invoice_number = int(re_number.search(inv.number).group(1) or -1)

            if invoice_number < 0:
                raise osv.except_osv(
                    _(u'AFIP Validation Error'),
                    _("Can't find invoice number. "
                      "Please check the journal sequence prefix and suffix "
                      "are not breaking the number generator."))

            # Build request dictionary
            if conn.id not in Requests:
                Requests[conn.id] = {}

            assert inv.currency_id.afip_code, \
                'Must defined afip_code for the currency.'

            Requests[conn.id][inv.id] = self._new_request(
                cr, uid, inv, journal, invoice_number)
            Inv2id[invoice_number] = inv.id
            Inv2number[invoice_number] = inv.number

        return self._save_cae(cr, uid, Inv2id, Inv2number, Requests)

    def _new_request(self, cr, uid, inv, journal, invoice_number):
        def _f_date(d):
            return d and d.replace('-', '')

        def _iva_filter(t):
            return 'IVA' in _get_parents(t.tax_code_id)

        def _not_iva_filter(t):
            return 'IVA' not in _get_parents(t.tax_code_id)

        def _remove_nones(d):
            return {k: v for k, v in d.iteritems() if v is not None}

        currency_obj = self.pool.get('res.currency')

        return _remove_nones({
            'CbteTipo': journal.journal_class_id.afip_code,
            'PtoVta': journal.point_of_sale,
            'Concepto': inv.afip_concept,
            'DocTipo': inv.partner_id.document_type_id.afip_code or '99',
            'DocNro': int(inv.partner_id.document_number
                          if inv.partner_id.document_type_id.afip_code
                          is not None
                          else False),
            'CbteDesde': invoice_number,
            'CbteHasta': invoice_number,
            'CbteFch': _f_date(inv.date_invoice),
            'ImpTotal': inv.amount_total,
            # TODO:
            # Averiguar como calcular el Importe Neto no Gravado
            'ImpTotConc': 0,
            'ImpNeto': inv.amount_untaxed,
            'ImpOpEx': inv.compute_all(
                line_filter=lambda line: len(line.invoice_line_tax_id) == 0
            )['amount_total'],
            'ImpIVA': inv.compute_all(
                tax_filter=_iva_filter)['amount_tax'],
            'ImpTrib': inv.compute_all(
                tax_filter=_not_iva_filter)['amount_tax'],
            'FchServDesde': _f_date(inv.afip_service_start)
            if inv.afip_concept != '1' else None,
            'FchServHasta': _f_date(inv.afip_service_end)
            if inv.afip_concept != '1' else None,
            'FchVtoPago': _f_date(inv.date_due)
            if inv.afip_concept != '1' else None,
            'MonId': inv.currency_id.afip_code,
            'MonCotiz': currency_obj.compute(
                cr, uid,
                inv.currency_id.id,
                inv.company_id.currency_id.id, 1.),
            'CbtesAsoc': {'CbteAsoc':
                          [c for c in
                           self.get_related_invoices(cr, uid, inv.id)]},
            'Tributos': {'Tributo':
                         [t for t in self.get_taxes(cr, uid, inv.id)]},
            'Iva': {'AlicIva':
                    [a for a in self.get_vat(cr, uid, inv.id)]},
            'Opcionales': {'Opcional':
                           [o for o in self.get_optionals(cr, uid, inv.id)]},
        })

    def _save_cae(self, cr, uid, Inv2id, Inv2number, Requests,
                  use_new_cursor=False):
        """
        Store and invoice_number in cae in database using new cursor.
        @param self: the invoice object.
        @param cr: database cursor.
        @param uid: The current user ID for security checks.
        @param Inv2id: Map of ids from invoice number.
        @param Inv2number: Map of odoo invoice number from invoice number.
        @param use_new_cursor: Set true to assign new cursor to commit changes.
                               This not working now, because the main cursor
                               lock the new.
        """
        conn_obj = self.pool.get('wsafip.connection')
        serv_obj = self.pool.get('wsafip.server')

        msg = False
        for c_id, req in Requests.iteritems():
            try:
                _cr_ = registry(cr.dbname).cursor() if use_new_cursor else cr
                conn = conn_obj.browse(_cr_, uid, c_id)
                res = conn.server_id.wsfe_get_cae(c_id, req)
                for k, v in res.iteritems():
                    if 'CAE' in v:
                        inv_id = Inv2id[k]
                        inv_number = Inv2number[k]
                        self.write(_cr_, uid, inv_id, {
                            'afip_cae': v['CAE'],
                            'afip_cae_due': v['CAEFchVto'],
                            'internal_number': inv_number,
                        })
                    else:
                        # Muestra un mensaje de error por la factura con error.
                        # Se cancelan todas las facturas del batch!
                        msg = 'Factura %s:\n' % k + '\n'.join(
                            [u'(%s) %s\n' % e for e in v['Errores']] +
                            [u'(%s) %s\n' % e for e in v['Observaciones']]
                        ) + '\n'
                if use_new_cursor:
                    _cr_.commit()
            except e:
                _logger.error("Error: %s" % e)
                if use_new_cursor:
                    _cr_.rollback()
            finally:
                if use_new_cursor:
                    try:
                        _cr_.close()
                    except Exception:
                        pass

        if msg:
            # TODO: Reenviar a las facturas que no pudieron ser validadas.
            raise osv.except_osv(_(u'AFIP Validation Error'), msg)

        return True

    def invoice_print(self, cr, uid, ids, context=None):
        '''
        This function prints the invoice and mark it as sent,
        so that we can see more easily the next step of the workflow
        Check if electronic invoice or normal invoice.
        '''
        assert len(ids) == 1, \
            'This option should only be used for a single id at a time.'
        self.write(cr, uid, ids, {'sent': True}, context=context)
        datas = {
            'ids': ids,
            'model': 'account.invoice',
            'form': self.read(cr, uid, ids[0], context=context)
        }
        is_electronic = bool(
            self.browse(cr, uid, ids[0]).journal_id.afip_connection_id)
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'l10n_ar_wsafip_fe.report_invoice'
            if is_electronic else 'account.report_invoice',
            'datas': datas,
            'nodestroy': True
        }

invoice()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
