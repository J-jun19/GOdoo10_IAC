# -*- coding: utf-8 -*-
{
    'name': "IAC Vendor Evaluation",
    'summary': """
        IAC Vendor Evaluation
        """,
    'description': """
        英华达供應商評鑒模块
    """,
    'author': "IAC",
    'website': "www.iac.com",
    "category" : "IAC",
    'version': '10.0.0.1',
    'depends': [
        'base', 'warning_box', 'oscg_vendor', 'oscg_po'
    ],
    # always loaded
    'data': [
        'views/base.xml',
        'views/vendor_evaluation.xml',
        'views/dclass_evaluation.xml',
        'wizard/evaluation_wizard.xml',
        'wizard/dclass_wizard.xml',
        'data/vendor_data.xml',
        'data/task.xml',
        'data/common_data.xml',
        'views/iac_supplier_company_risk.xml',
        'views/iac_bulletin.xml',
        'views/iac_bulletin_attachment.xml',
        'views/iac_vendor_exclude.xml',
        'views/iac_supplier_company_delete.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': True
}