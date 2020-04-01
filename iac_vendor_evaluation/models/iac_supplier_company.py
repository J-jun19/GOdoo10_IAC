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


class IacSupplierCompany(models.Model):
    """supplier company"""
    _inherit="iac.supplier.company"

    @api.model
    def update_score_weight(self,score_snapshot):
        """
        根据supplier_company 和score_list_id 更新分厂区评鉴的权重信息
        :param score_list_id:
        :return:
        """

        #获取不区分厂区的的总业务量
        self.env.cr.execute("""
            SELECT
                COALESCE(SUM (business_amount),0) business_amount_sum
            FROM
                iac_score_supplier_company
            WHERE
            score_snapshot =%s
            AND supplier_company_id =%s
                        """,(score_snapshot,self.id))
        pg_result = self.env.cr.dictfetchone()
        business_amount_sum=pg_result["business_amount_sum"]

        #获取分厂区的分数记录
        domain=[('score_snapshot','=',score_snapshot),('supplier_company_id','=',self.id)]
        sc_score_list=self.env["iac.score.supplier_company"].search(domain)
        for sc_score_rec in sc_score_list:
            vals={
            }
            if sc_score_rec.business_amount==0:
                vals["weight"]=0
            else:
                vals={
                    "weight":sc_score_rec.business_amount/business_amount_sum
                }
            sc_score_rec.write(vals)

