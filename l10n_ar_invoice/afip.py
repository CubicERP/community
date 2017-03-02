# -*- coding: utf-8 -*-
from openerp import api, models, _
from openerp import fields as Fields
from openerp.osv import fields, osv
from openerp import exceptions

import logging

_logger = logging.getLogger(__name__)

class afip_journal_template(osv.osv):
    _name = 'afip.journal_template'
    _columns = {
        'name': fields.char('Name', size=120),
        'code': fields.integer('Code'),
    }
afip_journal_template()

class afip_document_class(osv.osv):
    _name='afip.document_class'
    _description='Document class'
    _columns={
        'name': fields.char('Name', size=64, required=True),
        'description': fields.text('Description'),
        'responsability_relation_ids': fields.one2many('afip.responsability_relation','document_class_id', 'Reponsability relations'),
        'journal_class_ids': fields.one2many('afip.journal_class', 'document_class_id', 'Journal classes'),
    }
    _sql_constraints = [('name','unique(name)', 'Not repeat name!'),]
afip_document_class()

class afip_responsability(osv.osv):
    _name='afip.responsability'
    _description='VAT Responsability'
    _columns={
        'name': fields.char('Name', size=64, required=True),
        'code': fields.char('Code', size=8, required=True),
        'active': fields.boolean('Active'),
        'issuer_relation_ids': fields.one2many('afip.responsability_relation', 'issuer_id', 'Issuer relation'),
        'receptor_relation_ids': fields.one2many('afip.responsability_relation', 'receptor_id', 'Receptor relation'),
    }
    _sql_constraints = [('name','unique(name)', 'Not repeat name!'),
                        ('code','unique(code)', 'Not repeat code!')]
afip_responsability()

class afip_responsability_relation(osv.osv):
    _name='afip.responsability_relation'
    _description='Responsability relation'
    _columns={
        'name': fields.char('Name', size=64),
        'issuer_id': fields.many2one('afip.responsability', 'Issuer', required=True),
        'receptor_id': fields.many2one('afip.responsability', 'Receptor', required=True),
        'document_class_id': fields.many2one('afip.document_class', 'Document class', required=True),
        'active': fields.boolean('Active'),
    }
    _sql_constraints = [('main_constraints','unique(issuer_id, receptor_id, document_class_id)', 'Not configuration!'),
                        ('name','unique(name)', 'Not repeat name!')]
afip_responsability_relation()

class afip_journal_class(osv.osv):
    _name='afip.journal_class'
    _description='AFIP Journal types'
    _columns={
        'name': fields.char('Name', size=64, required=True),
        'code': fields.char('Code', size=8, required=True),
        'document_class_id': fields.many2one('afip.document_class', 'Document Class'),
        'type': fields.selection([
            ('sale', 'Sale'),
            ('sale_refund','Sale Refund'),
            ('purchase', 'Purchase'),
            ('purchase_refund','Purchase Refund'),
            ('cash', 'Cash'),
            ('bank', 'Bank and Cheques'),
            ('general', 'General'),
            ('situation', 'Opening/Closing Situation')
        ], 'Type', size=32, required=True,
             help="Select 'Sale' for Sale journal to be used at the time of making invoice."\
             " Select 'Purchase' for Purchase Journal to be used at the time of approving purchase order."\
             " Select 'Cash' to be used at the time of making payment."\
             " Select 'General' for miscellaneous operations."\
             " Select 'Opening/Closing Situation' to be used at the time of new fiscal year creation or end of year entries generation."),
        'afip_code': fields.integer('AFIP Code',required=True),
        'journal_ids': fields.one2many('account.journal', 'journal_class_id', 'Journals'),
        'active': fields.boolean('Active'),
        'product_types': fields.char('Product types',
                                     help='Only use products with this product types in this journals. '
                                     'Types must be a subset of adjust, consu and service separated by commas.'),
    }

    _sql_constraints = [('name','unique(name)', 'Not repeat name!')]
afip_journal_class()

class afip_document_type(osv.osv):
    _name = 'afip.document_type'
    _description='AFIP document types'
    _columns = {
        'name': fields.char('Name', size=120,required=True),
        'code': fields.char('Code', size=16,required=True),
        'afip_code': fields.integer('AFIP Code',required=True),
        'active': fields.boolean('Active'),
    }
afip_document_type()

class afip_concept_type(models.Model):
    _name = 'afip.concept_type'
    _description='AFIP concept types'

    name = Fields.Char('Name', size=120, required=True)
    afip_code = Fields.Integer('AFIP Code', required=True)
    active = Fields.Boolean('Active')
    product_types = Fields.Char(
        'Product types',
        help='Translate this product types to this AFIP concept. '
        'Types must be a subset of adjust, consu and service separated by commas.',
        required=True)

    @api.model
    def get_code(self, types):
        _logger.info("In Concept: %s" % types)
        types = set(t for t in types if isinstance(t, (unicode, str)))
        _logger.info("Concept: %s" % types)
        if not types:
            return False
        for concept in self.search([]):
            product_types = set([ s.strip() for s in concept.product_types.split(',')])
            if product_types == types:
                return str(concept.afip_code)
        raise exceptions.Warning(
            _('Cant compute AFIP concept from product types [%s].') % ','.join(types)
        )

    _sql_constraints = [('name','unique(name)', 'Not repeat name!')]
afip_concept_type()

class afip_tax_code(osv.osv):
    _inherit = 'account.tax.code'

    def _get_parent_afip_code(self, cr, uid, ids, field_name, args, context=None):
        r = {}

        for tc in self.read(cr, uid, ids, ['afip_code', 'parent_id'], context=context):
            _id = tc['id']
            if tc['afip_code']:
                r[_id] = tc['afip_code']
            elif tc['parent_id']:
                p_id = tc['parent_id'][0]
                r[_id] = self._get_parent_afip_code(cr, uid, [p_id], None, None)[p_id]
            else:
                r[_id] = 0

        return r

    _columns = {
        'afip_code': fields.integer('AFIP Code'),
        'parent_afip_code': fields.function(_get_parent_afip_code, type='integer', method=True, string='Parent AFIP Code', readonly=1),
    }

    def get_afip_name(self, cr, uid, ids, context=None):
        r = {}

        for tc in self.browse(cr, uid, ids, context=context):
            if tc.afip_code:
                r[tc.id] = tc.name
            elif tc.parent_id:
                r[tc.id] = tc.parent_id.get_afip_name()[tc.parent_id.id]
            else:
                r[tc.id] = False

        return r

afip_tax_code()

class afip_optional_type(osv.osv):
    _name = 'afip.optional_type'
    _description='AFIP optional types'
    _columns = {
        'name': fields.char('Name', size=120,required=True),
        'afip_code': fields.integer('AFIP Code',required=True),
        'apply_rule': fields.char('Apply rule'),
        'value_computation': fields.char('Value computation'),
        'active': fields.boolean('Active'),
    }
afip_optional_type()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
