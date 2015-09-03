# -*- coding: utf-8 -*-
from openerp.osv import fields, osv
from openerp.tools.translate import _
import re


class res_partner(osv.osv):
    _inherit = 'res.partner'

    _columns = {
        'responsability_id': fields.many2one(
            'afip.responsability',
            'Responsability'
        ),
        'document_type_id': fields.many2one(
            'afip.document_type',
            'Document type',
            on_change="onchange_document(vat,document_type_id,document_number)"
        ),
        'document_number': fields.char(
            'Document number',
            size=64, select=1,
            on_change="onchange_document(vat,document_type_id,document_number)"
        ),
        'iibb': fields.char('Ingresos Brutos', size=64),
        'start_date': fields.date('Inicio de actividades'),
    }

    def onchange_document(self, cr, uid, ids, vat, document_type,
                          document_number, context={}):
        v = {}
        m = None
        mod_obj = self.pool.get('ir.model.data')
        if document_number and \
                (u'afip.document_type', document_type) == \
                mod_obj.get_object_reference(
                    cr, uid, 'l10n_ar_invoice', 'dt_CUIT'):
            document_number = re.sub('[^1234567890]', '', str(document_number))
            if not self.check_vat_ar(document_number):
                m = {'title': _('Warning!'),
                     'message': _('VAT Number is wrong.\n'
                                  ' Please verify the number before continue.')}
            if vat is False:
                v['vat'] = 'AR%s' % document_number
            v['document_number'] = document_number
        return {'value': v,
                'warning': m}

    # TODO: v8
    # def onchange_vat(self, cr, uid, ids, vat, document_type, document_number,
    #                  context={}):
    #     """
    #     Not used because is complex to integrate.
    #     Could be associated to country?
    #     """
    #     country_obj = self.pool.get('res.country')
    #     doc_type_obj = self.pool.get('afip.document_type')

    #     cuit_document_type_id = doc_type_obj.search(cr, uid,
    #                                                 [('code', '=', 'CUIT')])

    #     v = {}
    #     if vat[:2].lower() == 'ar' and document_type is False and \
    #             document_number is False:
    #         v['document_type'] = cuit_document_type_id
    #         v['document_number'] = vat[2:]
    #     elif document_type is False and document_number is False:
    #         country_ids = country_obj.search(cr, uid,
    #                                          [('code', '=', vat[:2].upper())])
    #         iva_data = country_obj.read(cr, uid,
    #                                     country_ids,
    #                                     ['cuit_juridica', 'cuit_fisica'])
    #         v['document_type'] = cuit_document_type_id
    #         v['document_number'] = iva_data['cuit_juridica'
    #                                         if is_company else 'cuit_fisica']
    #     return { 'value': v }

    def afip_validation(self, cr, uid, ids, context={}):
        """
        Hay que validar si:
        - El partner no es de tipo 'consumidor final' tenga un CUIT asociado.
        - Si el CUIT es extranjero, hay que asignar a document_number y
          document_type los correspondientes a la interpretación argentina del
          CUIT.
        - Si es responsable monotributo hay que asegurarse que tenga VAT
          asignado. El documento y número de documento deberían ser DNI.
        - Si es Responsable Inscripto y Persona Jurídica indicar el CUIT copia
          del VAT.

        El objetivo es que en la generación de factura utilice la información de
        document_type y document_number.

        Otra opción es asignar a la argentina los prefijos: 'cuit' 'dni' 'ci',
        etc...

        Del prefijo se toma el número de documento. Que opinanará la comunidad?
        """

        for part in self.read(cr, uid, ids,
                              ['document_number', 'document_type_id',
                               'vat', 'is_vat_subject']):
            pass

    def prefered_journals(self, cr, uid, ids, company_id, type, context=None):
        """
        Devuelve la lista de journals disponibles para este partner.
        """
        # Set list of valid journals by partner responsability
        partner_obj = self.pool.get('res.partner')
        company_obj = self.pool.get('res.company')

        result = {}
        context = context or {}

        for partner in self.browse(cr, uid, ids):
            partner_id = partner.id
            partner = partner_obj.browse(cr, uid, partner_id)
            company = company_obj.browse(cr, uid, company_id)
            responsability = partner.responsability_id

            if responsability.issuer_relation_ids is None:
                return result

            type_map = {
                'out_invoice': ['sale'],
                'out_refund': ['sale_refund'],
                'in_invoice': ['purchase'],
                'in_refund': ['purchase_refund'],
            }

            if not company.partner_id:
                raise osv.except_osv(
                    _('Error!'),
                    _('Your company has not setted any partner'))

            if not company.partner_id.responsability_id:
                raise osv.except_osv(
                    _('Error!'),
                    _('Your company has not setted any responsability'))

            cr.execute(
                """
                SELECT DISTINCT J.id, J.name, IRSEQ.number_next
                FROM account_journal J
                LEFT join ir_sequence IRSEQ
                on (J.sequence_id = IRSEQ.id)
                LEFT join afip_journal_class JC
                on (J.journal_class_id = JC.id)
                LEFT join afip_document_class DC
                on (JC.document_class_id = DC.id)
                LEFT join afip_responsability_relation RR
                on (DC.id = RR.document_class_id)
                WHERE
                (RR.id is Null
                OR (RR.id is not Null
                AND RR.issuer_id = %s AND RR.receptor_id = %s)) AND
                J.type in %s AND
                J.id is not NULL AND
                J.sequence_id is not NULL
                AND IRSEQ.number_next is not NULL
                ORDER BY IRSEQ.number_next DESC;
                """, (company.partner_id.responsability_id.id,
                      partner.responsability_id.id,
                      tuple(type_map[type])))
            result[partner_id] = [x[0] for x in cr.fetchall()]

        return result


res_partner()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
