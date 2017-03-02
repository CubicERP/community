# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright (C) 2014 Otra localización argentina de Odoo.
# http://odoo-l10n-ar.github.io/
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from openerp.osv import fields, osv

class country(osv.osv):
        _inherit = 'res.country'
        _columns = {
                'afip_code': fields.char('AFIP code', size=64, help='Codigo oficial del AFIP.'),
        }

class country_state(osv.osv):
        _inherit = 'res.country.state'
        _columns = {
                'afip_code': fields.char('AFIP code', size=64, help='Codigo oficial del AFIP.'),
        }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
