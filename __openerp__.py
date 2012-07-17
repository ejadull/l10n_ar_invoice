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
{
    'name':     'Argentina - Generador de Talonarios',
    'version':  '2.1',
    'author':   'OpenERP - Team de Localización Argentina',
    'category': 'Localization/Argentina',
    'website':  'https://launchpad.net/~openerp-l10n-ar-localization',
    'license':  'GPL-3',
    'description': """
Módulo de Facturación de la localización Argentina

Incluye:

  - Configuración de libros, diarios y otros detalles para facturación argentina.
  - Wizard para configurar los talonarios necesarios para facturar.
""",
    'depends': [
        'l10n_chart_ar_generic',
    ],
    'init_xml': [],
    'demo_xml': [],
    'test': [
        'test/wizard_installer.yml',
    ],
    'update_xml': [
        'data/invoice_installer.xml',
        'data/reports.xml',
    ],
    'active': False,
    'installable': True,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: