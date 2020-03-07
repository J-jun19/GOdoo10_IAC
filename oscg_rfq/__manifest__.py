# -*- coding: utf-8 -*-
{
    'name': "IAC RFQ",

    'summary': """

        """,

    'description': """

    """,

    'author': "www.oscg.cn",
    'website': "www.oscg.cn",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Extra Tools',
    'version': '10.0.0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'oscg_vendor','oscg_po','mail','base_import'],

    # always loaded
    'data': [
        #'security/ir_security.xml',
        #'view/iacRfqView.xml',
        #'view/iacASNView.xml',
        #'data/mail_template_data.xml',

        'data/init_data.xml',
        #'data/iac.rfq.qh.csv',

        'view/iac_rfq_common_view.xml',
        'view/iac_rfq_as_view.xml',
        'view/iac_rfq_mm_view.xml',
        'view/iac_rfq_mass_view.xml',
        'view/iac_rfq_quote_view.xml',
        'view/iac_rfq_user_group_view.xml',
        'view/iac_rfq_create_view.xml',
        'view/iac_rfq_change_term_view.xml',
        'view/iac_rfq_group_view.xml',

        'view/iac_asn_common_view.xml',
        'view/iac_asn_buyer_view.xml',
        'view/iac_asn_vendor_view.xml',
        'view/iac_asn_jit_rule_view.xml',
        'view/iac_asn_max_qty_view.xml',
        'view/iac_asn_po_line_buyer_view.xml',
        'view/iac_asn_po_line_vendor_view.xml',
        'view/iac_asn_vendor_create_entry.xml',
        'view/iac_asn_vendor_create_godown.xml',
        'view/iac_check_list_detailed.xml',
        'view/iac_entry_godown_detailed_list.xml',
        'view/iac_asn_vendor_create_checklist.xml',
        'view/iac_asn_buy_sell_view.xml',
        'view/iac_rfq_cost_up_reason_view.xml',
        'view/iac_asn_vmi_view.xml',
        'view/iac_asn_clean_view.xml',
        'view/iac_asn_menu_item_view.xml',
        'view/iac_rfq_menu_item_view.xml',

    ],
}