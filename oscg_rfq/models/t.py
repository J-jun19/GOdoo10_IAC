# -*- coding: utf-8 -*-

import erppeek
"""
erppeek使用例子：
>>> import erppeek
>>> api = erppeek.Client('http://localhost:8069', 'todo','admin', 'admin')
>>> api.common.version()
>>> api.count('res.partner', [])
>>> api.search('res.partner', [('country_id', ' ', 'be'), ('parent_id', '!=', False)])
>>> api.read('res.partner', [44], ['id', 'name', 'parent_id'])

>>> m = api.model('res.partner')
>>> m = api.ResPartner
>>> m.count([('name', 'like', 'Packt%')])
>>> 1
>>> m.search([('name', 'like', 'Packt%')])
>>> [30]

注意：调用model的自定义函数时，该函数必须有返回值
"""
if __name__=="__main__":

    api = erppeek.Client('http://localhost:8070', 'IAC_DB', 'admin', 'admin')

    model = api.model('iac.asn.vmi.sap')
    r = model.job_sap_rpc()
    print r

