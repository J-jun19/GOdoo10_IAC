# -*- coding: utf-8 -*-
from odoo import models, fields, api, exceptions, _

         
# class IacVendorScoreExclude(models.Model):
#     """
#     免评Supplier Company
#     """
#     _name = 'iac.score.exclude'
#     _description = "Exclude Vendor"
#
#     supplier_company_id = fields.Many2one('iac.supplier.company', string="Supplier Company")
#     active = fields.Boolean(
#         'Active', default=True,
#         help="If unchecked, it will allow you to hide the definition without removing it.")

    
# class IacScoreExcludePlant(models.Model):
#     """
#     按厂区免评Supplier Company
#     """
#     _name = "iac.score.exclude.plant"
#     _description = "Exclude Vendor Plant"
#
#     plant_id = fields.Many2one('pur.org.data', string="Plant")
#     supplier_company_id = fields.Many2one('iac.supplier.company', string="Supplier Company")
#     active = fields.Boolean(
#         'Active', default=True,
#         help="If unchecked, it will allow you to hide the definition without removing it.")