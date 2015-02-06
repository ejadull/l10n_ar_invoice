# -*- coding: utf-8 -*-
##############################################################################
#
# Copyright (C) 2012 OpenERP - Team de Localización Argentina.
# https://launchpad.net/~openerp-l10n-ar-localization
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
from openerp import api, models, fields, _
from openerp.exceptions import except_orm, Warning, RedirectWarning
from datetime import date, timedelta

_all_taxes = lambda x: True
_all_except_vat = lambda x: x.tax_code_id.parent_id.name != 'IVA'

class account_invoice_line(models.Model):
    """
    Line of an invoice. Compute pirces with and without vat, for unit or line quantity.
    """
    _name = "account.invoice.line"
    _inherit = "account.invoice.line"

    @api.one
    @api.depends('quantity','discount','price_unit','invoice_line_tax_id','product_id','invoice_id.partner_id','invoice_id.currency_id')
    def compute_price(self, context=None):
        self.price_unit_vat_included         = self.price_calc(use_vat=True, quantity=1)
        self.price_subtotal_vat_included     = self.price_calc(use_vat=True)
        self.price_unit_not_vat_included     = self.price_calc(use_vat=False, quantity=1)
        self.price_subtotal_not_vat_included = self.price_calc(use_vat=False)

    price_unit_vat_included         = fields.Float(compute='compute_price')
    price_subtotal_vat_included     = fields.Float(compute='compute_price')
    price_unit_not_vat_included     = fields.Float(compute='compute_price')
    price_subtotal_not_vat_included = fields.Float(compute='compute_price')

    @api.v8
    def price_calc(self, use_vat=True, tax_filter=None, quantity=None, discount=None, context=None):
        assert len(self) == 1, "Use price_calc with one instance"
        _tax_filter = tax_filter or ( use_vat and _all_taxes ) or _all_except_vat
        _quantity = quantity if quantity is not None else self.quantity
        _discount = discount if discount is not None else self.discount
        _price = self.price_unit * (1-(_discount or 0.0)/100.0)

        taxes = self.invoice_line_tax_id.filtered(_tax_filter).compute_all(
            _price, _quantity,product=self.product_id,partner=self.invoice_id.partner_id
        )
        return self.invoice_id.currency_id.round(taxes['total_included']) \
                if self.invoice_id \
                else taxes['total_included']

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

            _round = (lambda x: line.invoice_id.currency_id.round(x)) if line.invoice_id else (lambda x: x)
            res[line.id] = {
                'amount_untaxed': _round(taxes['total']),
                'amount_tax': _round(taxes['total_included'])-_round(taxes['total']),
                'amount_total': _round(taxes['total_included']), 
                'taxes': taxes['taxes'],
            }
        return res.get(len(self)==1 and res.keys()[0], res)

account_invoice_line()

def _calc_concept(product_types):
    if product_types == set(['consu']):
        concept = '1'
    elif product_types == set(['service']):
        concept = '2'
    elif product_types == set(['consu','service']):
        concept = '3'
    else:
        concept = False
    return concept

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
        r = {}
        for inv in self:
            concept = False
            product_types = set([ line.product_id.type for line in inv.invoice_line ])
            inv.afip_concept = _calc_concept(product_types)

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

    afip_concept = fields.Selection([('1','Consumible'), ('2','Service'), ('3','Mixted')],
                                    compute="_get_concept",
                                    store=False,
                                    help="AFIP invoice concept.") 
    afip_service_start = fields.Date('Service Start Date', default=_get_service_begin_date)
    afip_service_end = fields.Date('Service End Date', default=_get_service_end_date)

    def afip_validation(self):
        """
        Check basic AFIP request to generate invoices.
        """
        for invoice in self:
            # If parter is not in Argentina, ignore it.
            if invoice.company_id.partner_id.country_id.name != 'Argentina':
                continue

            # Check if you choose the right journal.
            if invoice.type == 'out_invoice' and invoice.journal_id.journal_class_id.afip_code not in [1,6,11,51,19, 2,7,12,52,20]:
                raise except_orm(_('Wrong Journal'),
                                 _('Out invoice journal must have a valid journal class.'))
            if invoice.type == 'out_refund' and invoice.journal_id.journal_class_id.afip_code not in [3,8,13,53,21]:
                raise except_orm(_('Wrong Journal'),
                                 _('Out invoice journal must have a valid journal class.'))

            # Partner responsability ?
            if not invoice.partner_id.responsability_id:
                raise except_orm(_('No responsability'),
                                 _('Your partner have not afip responsability assigned. Assign one please.'))

            # Take responsability classes for this journal
            invoice_class = invoice.journal_id.journal_class_id.document_class_id
            resp_class = self.env['afip.responsability_relation'].search([
                ('document_class_id','=', invoice_class.id),
                ('issuer_id.code','=',invoice.journal_id.company_id.partner_id.responsability_id.code)
            ])

            # You can emmit this document?
            if not resp_class:
                raise except_orm(_('Invalid emisor'),
                                 _('Your responsability with AFIP dont let you generate this kind of document.'))

            # Partner can receive this document?
            resp_class = self.env['afip.responsability_relation'].search([
                ('document_class_id','=', invoice_class.id),
                ('receptor_id.code','=',invoice.partner_id.responsability_id.code)
            ])
            if not resp_class:
                raise except_orm(_('Invalid receptor'),
                                 _('Your partner cant receive this document. Check AFIP responsability of the partner, or Journal Account of the invoice.'))

            # If Final Consumer have pay more than 1000$, you need more information to generate document.
            if invoice.partner_id.responsability_id.code == 'CF' and invoice.amount_total > 1000 and \
               (invoice.partner_id.document_type.code in [ None, 'Sigd' ] or invoice.partner_id.document_number is None):
                raise except_orm(_('Partner without Identification for total invoices > $1000.-'),
                                 _('You must define valid document type and number for this Final Consumer.'))
        return True

    def compute_all(self, cr, uid, ids, line_filter=lambda line: True, tax_filter=lambda tax: True, context=None):
        res = {}
        for inv in self.browse(cr, uid, ids, context=context):
            amounts = []
            for line in inv.invoice_line:
                if line_filter(line):
                    amounts.append(line.compute_all(tax_filter=tax_filter, context=context))

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

        return res.get(len(ids)==1 and ids[0], res)

    @api.multi
    def onchange_partner_id(self, type, partner_id, date_invoice=False,
            payment_term=False, partner_bank_id=False, company_id=False):

        result = super(account_invoice,self).onchange_partner_id(
                       type, partner_id, date_invoice, payment_term,
                       partner_bank_id, company_id)

        if partner_id:
            # Set list of valid journals by partner responsability
            # partner_obj = self.pool.get('res.partner')
            company_obj = self.pool.get('res.company')
            partner = self.env['res.partner'].browse(partner_id)
            company = self.env['res.company'].browse(company_id)
            responsability = partner.responsability_id

            if not responsability:
                    result['warning']={'title': _('The partner has not set any fiscal responsability'),
                                       'message': _('Please, set partner fiscal responsability in the partner form before continuing.')}
                    return result

            if responsability.issuer_relation_ids is None:
                return result

            document_class_set = set([ i.document_class_id.id for i in responsability.issuer_relation_ids ])

            type_map = {
                'out_invoice': ['sale'],
                'out_refund': ['sale_refund'],
                'in_invoice': ['purchase'],
                'in_refund': ['purchase_refund'],
            }

            if not company.partner_id.responsability_id.id:
                result['warning']={'title': _('Your company has not set any fiscal responsability'),
                                   'message': _('Please, set your company responsability in the company form before continuing.')}
                return result

            self._cr.execute("""
                       SELECT DISTINCT J.id, J.name, IRSEQ.number_next
                       FROM account_journal J
                       LEFT join ir_sequence IRSEQ on (J.sequence_id = IRSEQ.id)
                       LEFT join afip_journal_class JC on (J.journal_class_id = JC.id)
                       LEFT join afip_document_class DC on (JC.document_class_id = DC.id)
                       LEFT join afip_responsability_relation RR on (DC.id = RR.document_class_id)
                       WHERE
                       (RR.id is Null OR (RR.id is not Null AND RR.issuer_id = %s AND RR.receptor_id = %s)) AND
                       J.type in %s AND                        
                       J.id is not NULL AND
                       J.sequence_id is not NULL
                       AND IRSEQ.number_next is not NULL
                       ORDER BY IRSEQ.number_next DESC;
                       """, (company.partner_id.responsability_id.id, partner.responsability_id.id, tuple(type_map[type])))
            accepted_journal_ids = [ x[0] for x in self._cr.fetchall() ]

            if 'domain' not in result: result['domain'] = {}
            if 'value' not in result: result['value'] = {}

            if accepted_journal_ids:
                result['domain'].update({
                    'journal_id': [('id','in', accepted_journal_ids)],
                })
                result['value'].update({
                    'journal_id': accepted_journal_ids[0],
                })
            else:
                result['domain'].update({
                    'journal_id': [('id','in',[])],
                })
                result['value'].update({
                    'journal_id': False,
                })

        return result

account_invoice()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

