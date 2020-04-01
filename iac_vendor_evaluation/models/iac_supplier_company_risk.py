# -*- coding: utf-8 -*-
import pytz
import time
import odoo
from datetime import datetime
from odoo import models, fields, api,odoo_env
from odoo.tools.translate import _
from odoo.exceptions import UserError, ValidationError
from dateutil.relativedelta import relativedelta
import pdb
from odoo.odoo_env import odoo_env
from functools import wraps
import  traceback
import threading


class IacSupplierCompanyRisk(models.Model):
    """supplier company 风险评定"""
    _name = "iac.supplier.company.risk"
    _description = u"IAC Supplier Company Risk Level"
    _order = 'supplier_company_code desc'

    supplier_company_code = fields.Char(string="Company No",index=True)
    supplier_company_name = fields.Char(string="Company Name")
    supplier_company_id = fields.Many2one('iac.supplier.company',  string="Supplier Company")
    score_snapshot = fields.Char(string='Score Snapshot', index=True)
    calculate_level=fields.Selection([('low','Low'),('medium','Medium'),('high','High')],string='Calculate Level')
    user_level=fields.Selection([('low','Low'),('medium','Medium'),('high','High')],string='User Level')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submit', 'Submit'),
    ], string='Status',  index=True, copy=False, default='submit')


    # @api.multi
    # def action_submit_supplier_company_risk(self):
    #     """
    #     QM leader核准class 調整，拒绝
    #     :return:
    #     """
    #     for supplier_company_risk_id in self.ids:
    #         risk_rec=self.env["iac.supplier.company.risk"].browse(supplier_company_risk_id)
    #         if risk_rec.state == 'draft' and risk_rec.user_level!=False:
    #             risk_rec.write({"state":"submit"})
    #     return self.env['warning_box'].info(title=u"提示信息", message=u"提交已经完成！")

