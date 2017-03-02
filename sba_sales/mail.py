from openerp.osv import osv,fields
from datetime import date

class mail_message(osv.osv):
	_name = "mail.message"
	_inherit = "mail.message"

	_columns = {
	        'no_auto_thread': fields.boolean('No threading for answers',
       		     help='Answers do not go in the original document\' discussion thread. This has an impact on the generated message-id.'),
		}

mail_message()

