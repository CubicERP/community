# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import fields, osv
from openerp.tools.translate import _
from datetime import datetime


class call_assign(osv.osv_memory):
    _name = 'crm.phonecall.assignment'
    _description = 'CRM Phonecall Assignment'

    import pdb;pdb.set_trace()
    _columns = {
        'telemarketer_id': fields.many2one('res.users', 'TeleMarketer', required=True),
        'campaign_name': fields.char('Campaña'),
    }
    _defaults = {
        'telemarketer_id': 1,
    }

    """
    def assign_call(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        datas = {'ids': context.get('active_ids', [])}
        res = self.read(cr, uid, ids, ['telemarketer_id','campaign_name'], context=context)
        res = res and res[0] or {}
        res['telemarketer_id'] = res['telemarketer_id'][0]

	partner_obj = self.pool.get('res.partner')
	phonecall_obj = self.pool.get('crm.phonecall')
	for partner in partner_obj.browse(cr,uid,ids):
		vals_phonecall = {
			'partner_id': partner.id,
			'responsible': res['telemarketer_id'],
			'name': partner_id.name
			}	
		return_id = phonecall_obj.create(cr,uid,vals_phonecall)

        return {}
	"""
call_asign()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

